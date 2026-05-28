from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from typing import Any

from rich.console import Console

from ...core import MQTTClient
from ..common import publish_drc_down

console = Console()

_SEQ_LOCK = threading.Lock()
_SEQ_COUNTER = int(time.time() * 1000)


def next_seq() -> int:
    """生成递增 seq，保证指令顺序性。"""
    global _SEQ_COUNTER
    now = int(time.time() * 1000)
    with _SEQ_LOCK:
        if now <= _SEQ_COUNTER:
            _SEQ_COUNTER += 1
        else:
            _SEQ_COUNTER = now
        return _SEQ_COUNTER


def publish(mqtt_client: MQTTClient, payload: dict[str, Any]) -> None:
    publish_drc_down(mqtt_client, payload)


def wait_for_drc_reply(
    mqtt_client: MQTTClient,
    *,
    method: str,
    seq: int,
    timeout: float,
    send_fn: Callable[[], None],
) -> dict:
    if not mqtt_client.client:
        raise RuntimeError("MQTT client is not connected")

    result_box: dict = {"result": None, "raw": None}
    done = threading.Event()
    original_on_message = mqtt_client.client.on_message

    def on_message(client, userdata, msg):
        payload = _decode_payload(msg.payload)
        if payload.get("method") == method and payload.get("seq") == seq:
            data = payload.get("data", {})
            result_box["result"] = data.get("result")
            result_box["raw"] = payload
            done.set()
        if original_on_message:
            original_on_message(client, userdata, msg)

    mqtt_client.client.on_message = on_message
    try:
        send_fn()
        if not done.wait(timeout):
            raise TimeoutError(f"{method} timeout")
    finally:
        mqtt_client.client.on_message = original_on_message

    result = result_box.get("result")
    return {
        "ok": result in (0, None),
        "result": result,
        "seq": seq,
        "raw": result_box.get("raw"),
    }


def _decode_payload(payload: bytes) -> dict:
    try:
        return json.loads(payload.decode())
    except Exception:
        return {}

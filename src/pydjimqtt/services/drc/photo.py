from __future__ import annotations

import json
import threading

from ...core import MQTTClient
from .replies import console, next_seq, publish


def take_photo(
    mqtt_client: MQTTClient,
    payload_index: str,
    seq: int | None = None,
    debug_full_request: bool = False,
) -> None:
    """发送拍照指令（单次发送，Fire-and-forget）"""
    if not payload_index:
        console.print("[red]✗ payload_index 不能为空[/red]")
        raise ValueError("payload_index must be a non-empty string")

    payload = {
        "seq": next_seq() if seq is None else seq,
        "method": "drc_camera_photo_take",
        "data": {"payload_index": payload_index},
    }
    try:
        if debug_full_request:
            from ...utils import print_json_message

            print_json_message(
                "📤 发送 MQTT 请求 (drc_camera_photo_take)",
                {
                    "topic": f"thing/product/{mqtt_client.gateway_sn}/drc/down",
                    "qos": 0,
                    "payload": payload,
                },
                "blue",
            )
        publish(mqtt_client, payload)
        console.print(f"[cyan]→[/cyan] 拍照指令已发送 (payload: {payload_index})")
    except Exception as exc:
        console.print(f"[red]✗ 拍照指令发送失败: {exc}[/red]")
        raise


def take_photo_wait(
    mqtt_client: MQTTClient,
    payload_index: str,
    timeout: float = 10.0,
    seq: int | None = None,
    debug_full_request: bool = False,
    debug_full_response: bool = False,
    send_photo=take_photo,
) -> dict:
    """发送拍照指令并等待结果回包。"""
    if not mqtt_client.client:
        raise RuntimeError("MQTT client is not connected")

    seq = next_seq() if seq is None else seq
    result_box: dict = {"result": None, "status": None, "raw": None}
    done = threading.Event()
    original_on_message = mqtt_client.client.on_message

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            payload = {}
        if payload.get("method") == "drc_camera_photo_take" and payload.get("seq") == seq:
            data = payload.get("data", {})
            result_box["result"] = data.get("result")
            result_box["status"] = data.get("status")
            result_box["raw"] = payload
            if debug_full_response:
                from ...utils import print_json_message

                print_json_message(
                    "📥 接收 MQTT 响应 (drc_camera_photo_take)",
                    {"topic": msg.topic, "payload": payload},
                    "green",
                )
            done.set()
        if original_on_message:
            original_on_message(client, userdata, msg)

    mqtt_client.client.on_message = on_message
    try:
        send_photo(
            mqtt_client,
            payload_index=payload_index,
            seq=seq,
            debug_full_request=debug_full_request,
        )
        if not done.wait(timeout):
            raise TimeoutError("drc_camera_photo_take timeout")
    finally:
        mqtt_client.client.on_message = original_on_message

    result = result_box.get("result")
    return {
        "ok": result == 0,
        "result": result,
        "status": result_box.get("status"),
        "seq": seq,
        "payload_index": payload_index,
        "raw": result_box.get("raw"),
    }

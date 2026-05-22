from __future__ import annotations

import json
import time
from typing import Callable, Any

from ..core import MQTTClient


def send_screen_drag(
    mqtt_client: MQTTClient,
    *,
    payload_index: str,
    pitch_speed: float,
    seq: int | None = None,
) -> int:
    if mqtt_client.client is None:
        raise RuntimeError("MQTT client is not connected")
    if seq is None:
        seq = int(time.time() * 1000)

    topic = f"thing/product/{mqtt_client.gateway_sn}/drc/down"
    payload = {
        "seq": seq,
        "method": "drc_camera_screen_drag",
        "data": {
            "payload_index": payload_index,
            "locked": False,
            "pitch_speed": pitch_speed,
            "yaw_speed": 0,
        },
    }
    mqtt_client.client.publish(topic, json.dumps(payload), qos=0)
    return seq


def send_screen_drag_pulse(
    mqtt_client: MQTTClient,
    *,
    payload_index: str,
    pitch_speed: float,
    duration: float,
    frequency_hz: float = 10.0,
    sleep_fn: Callable[[float], Any] = time.sleep,
) -> None:
    interval = 1.0 / frequency_hz
    deadline = time.monotonic() + max(duration, 0.0)
    send_screen_drag(
        mqtt_client,
        payload_index=payload_index,
        pitch_speed=pitch_speed,
    )
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        sleep_fn(min(interval, remaining))
        if deadline - time.monotonic() > 0:
            send_screen_drag(
                mqtt_client,
                payload_index=payload_index,
                pitch_speed=pitch_speed,
            )

    send_screen_drag(
        mqtt_client,
        payload_index=payload_index,
        pitch_speed=0,
    )

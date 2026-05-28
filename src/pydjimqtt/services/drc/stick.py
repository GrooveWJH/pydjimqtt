from __future__ import annotations

import json
import threading

from ...core import MQTTClient
from .replies import console, next_seq, publish


def send_stick_control(
    mqtt_client: MQTTClient,
    roll: int = 1024,
    pitch: int = 1024,
    throttle: int = 1024,
    yaw: int = 1024,
    seq: int | None = None,
) -> None:
    """发送 DRC 杆量控制指令（单次发送，调用方控制频率）"""
    for name, value in (
        ("roll", roll),
        ("pitch", pitch),
        ("throttle", throttle),
        ("yaw", yaw),
    ):
        if not 364 <= value <= 1684:
            console.print(f"[red]✗ {name} 超出范围: {value} (应在 364-1684)[/red]")
            raise ValueError(f"{name} must be in range [364, 1684], got {value}")
    publish(
        mqtt_client,
        {
            "seq": next_seq() if seq is None else seq,
            "method": "stick_control",
            "data": {"roll": roll, "pitch": pitch, "throttle": throttle, "yaw": yaw},
        },
    )


def drone_emergency_stop(mqtt_client: MQTTClient, seq: int | None = None) -> int:
    """DRC 飞行器急停（停止水平运动，Fire-and-forget）"""
    seq = next_seq() if seq is None else seq
    try:
        publish(mqtt_client, {"seq": seq, "method": "drone_emergency_stop", "data": {}})
        console.print(f"[bright_yellow]⚠ 急停指令已发送 (seq: {seq})[/bright_yellow]")
    except Exception as exc:
        console.print(f"[red]✗ 急停指令发送失败: {exc}[/red]")
        raise
    return seq


def drone_emergency_stop_wait(
    mqtt_client: MQTTClient, timeout: float = 3.0, seq: int | None = None
) -> dict:
    """发送急停指令并等待 drc/up 回包。"""
    if not mqtt_client.client:
        raise RuntimeError("MQTT client is not connected")

    seq = next_seq() if seq is None else seq
    result_box: dict = {"result": None}
    done = threading.Event()
    original_on_message = mqtt_client.client.on_message

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            payload = {}
        if payload.get("method") == "drone_emergency_stop" and payload.get("seq") == seq:
            data = payload.get("data", {})
            result_box["result"] = data.get("result")
            done.set()
        if original_on_message:
            original_on_message(client, userdata, msg)

    mqtt_client.client.on_message = on_message
    try:
        drone_emergency_stop(mqtt_client, seq=seq)
        if not done.wait(timeout):
            raise TimeoutError("drone_emergency_stop timeout")
    finally:
        mqtt_client.client.on_message = original_on_message

    result = result_box.get("result")
    return {"ok": result == 0, "result": result, "seq": seq}

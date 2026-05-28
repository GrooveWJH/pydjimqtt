from __future__ import annotations

import time
import uuid
from typing import Any

from ...core import MQTTClient, ServiceCaller
from ..common import call_service, publish_drc_down, console


def return_home(caller: ServiceCaller) -> dict:
    """一键返航"""
    console.print("[cyan]执行一键返航...[/cyan]")
    return call_service(caller, "return_home", data=None, success_msg="返航指令已发送")


def fly_to_point(
    caller: ServiceCaller,
    latitude: float,
    longitude: float,
    height: float,
    max_speed: int = 12,
    fly_to_id: str | None = None,
) -> str:
    """飞向目标点"""
    if fly_to_id is None:
        fly_to_id = str(uuid.uuid4())
    console.print(
        f"[cyan]飞向目标点 (lat: {latitude:.6f}, lon: {longitude:.6f}, h: {height:.1f}m)...[/cyan]"
    )
    call_service(
        caller,
        "fly_to_point",
        {
            "fly_to_id": fly_to_id,
            "max_speed": max_speed,
            "points": [{"latitude": latitude, "longitude": longitude, "height": height}],
        },
        "Fly-to 指令已发送",
    )
    return fly_to_id


def send_stick_control(
    mqtt_client: MQTTClient,
    roll: int = 1024,
    pitch: int = 1024,
    throttle: int = 1024,
    yaw: int = 1024,
) -> None:
    """发送 DRC 杆量控制指令（无回包机制）"""
    for name, value in (
        ("roll", roll),
        ("pitch", pitch),
        ("throttle", throttle),
        ("yaw", yaw),
    ):
        if not (364 <= value <= 1684):
            raise ValueError(f"{name} 必须在 [364, 1684] 范围内，当前值: {value}")

    payload: dict[str, Any] = {
        "seq": int(time.time() * 1000),
        "method": "stick_control",
        "data": {"roll": roll, "pitch": pitch, "throttle": throttle, "yaw": yaw},
    }
    publish_drc_down(mqtt_client, payload)

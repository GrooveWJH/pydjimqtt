from __future__ import annotations

import time

from ...core import MQTTClient
from ..common import publish_drc_down, console


def reset_gimbal(mqtt_client: MQTTClient, payload_index: str, reset_mode: int) -> None:
    """重置云台（DRC 下行指令，无回包机制）"""
    reset_mode_names = {0: "回中", 1: "向下", 2: "偏航回中", 3: "俯仰向下"}
    mode_name = reset_mode_names.get(reset_mode, f"未知模式({reset_mode})")
    if reset_mode not in reset_mode_names:
        raise ValueError(f"reset_mode 必须在 [0, 3] 范围内，当前值: {reset_mode}")

    payload = {
        "seq": int(time.time() * 1000),
        "method": "drc_gimbal_reset",
        "data": {"payload_index": payload_index, "reset_mode": reset_mode},
    }
    publish_drc_down(mqtt_client, payload)
    console.print(f"[bright_green]✓ 云台{mode_name}指令已发送[/bright_green]")

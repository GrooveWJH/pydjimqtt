from __future__ import annotations

import time

from rich.console import Console

from ...services import change_live_lens, reset_gimbal, set_camera_zoom
from ...utils import build_video_id
from ..runner import MissionRunner

console = Console()


def hover_between_waypoints(
    runners: list[MissionRunner],
    fly_to_ids: dict[str, str],
    wp_index: int,
    hover_seconds: float,
    show_progress: bool,
) -> None:
    if show_progress:
        console.print(f"[bright_cyan]━━━ 航点 {wp_index} 悬停操作 ━━━[/bright_cyan]")
        console.print(
            f"[bright_yellow]悬停 {hover_seconds:.1f} 秒，切换zoom镜头 + 云台朝下 + 变焦3倍[/bright_yellow]"
        )
    for runner in runners:
        _prepare_camera_for_hover(runner, fly_to_ids, show_progress)
    time.sleep(hover_seconds)


def _prepare_camera_for_hover(
    runner: MissionRunner,
    fly_to_ids: dict[str, str],
    show_progress: bool,
) -> None:
    mqtt = runner.mqtt
    callsign = runner.config.get("callsign", "UAV")
    if callsign not in fly_to_ids:
        return
    try:
        payload_index = mqtt.get_payload_index() or "88-0-0"
        _switch_zoom_lens(runner, show_progress)
        if show_progress:
            console.print(f"[bright_cyan][{callsign}] 云台朝下...[/bright_cyan]")
        reset_gimbal(mqtt, payload_index=payload_index, reset_mode=1)
        if show_progress:
            console.print(f"[bright_cyan][{callsign}] 变焦3倍...[/bright_cyan]")
        set_camera_zoom(mqtt, payload_index=payload_index, zoom_factor=3.0, camera_type="zoom")
    except Exception as exc:
        if show_progress:
            console.print(f"[bright_yellow]⚠ [{callsign}] 云台/变焦控制失败: {exc}[/bright_yellow]")


def _switch_zoom_lens(runner: MissionRunner, show_progress: bool) -> None:
    mqtt = runner.mqtt
    caller = runner.caller
    callsign = runner.config.get("callsign", "UAV")
    try:
        video_id = build_video_id(mqtt, video_index="zoom-0")
        if show_progress:
            console.print(f"[bright_cyan][{callsign}] 切换到zoom镜头...[/bright_cyan]")
        change_live_lens(caller, video_id=video_id, video_type="zoom")
    except Exception as exc:
        if show_progress:
            console.print(f"[bright_yellow]⚠ [{callsign}] 切换镜头失败: {exc}[/bright_yellow]")

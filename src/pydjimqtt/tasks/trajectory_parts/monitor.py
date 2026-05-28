from __future__ import annotations

import time

from rich.console import Console

from ..runner import MissionRunner
from .state import update_mission_state_file

console = Console()
TERMINAL_STATUSES = {"wayline_ok", "wayline_failed", "wayline_cancel"}


def monitor_runner_waypoint(
    runner: MissionRunner,
    fly_to_id: str,
    wp_index: int,
    show_progress: bool,
    debug: bool,
) -> bool:
    callsign = runner.config.get("callsign", "UAV")
    try:
        if debug:
            console.print(f"[dim]🐛 [{callsign}] 等待 fly_to_id={fly_to_id[:8]}... 的事件[/dim]")
        return _monitor_loop(runner, fly_to_id, wp_index, show_progress, debug)
    except TimeoutError as exc:
        console.print(f"[bold bright_red]✗ [{callsign}] 航点 {wp_index} 超时[/bold bright_red]")
        console.print(f"[dim]   {exc}[/dim]")
        return False
    except Exception as exc:
        console.print(f"[bold bright_red]✗ [{callsign}] 航点 {wp_index} 异常[/bold bright_red]")
        console.print(f"[dim]   {exc}[/dim]")
        return False


def _monitor_loop(
    runner: MissionRunner, fly_to_id: str, wp_index: int, show_progress: bool, debug: bool
) -> bool:
    start_time = time.time()
    last_print_time = 0.0
    while True:
        if not runner.running:
            update_mission_state_file(runner, wp_index, "已取消")
            return False
        if time.time() - start_time > 120.0:
            raise TimeoutError(
                f"[{runner.config.get('callsign', 'UAV')}] 等待 fly_to_id={fly_to_id[:8]}... 的事件超时（120秒）"
            )
        progress = runner.mqtt.get_flyto_progress()
        if progress.get("fly_to_id") == fly_to_id:
            status = progress.get("status")
            last_print_time = _print_progress(
                runner, progress, wp_index, status, last_print_time, show_progress
            )
            if debug and status in TERMINAL_STATUSES:
                console.print(
                    f"[dim]🐛 [{runner.config.get('callsign', 'UAV')}] 收到终止事件: {progress}[/dim]"
                )
            if status in TERMINAL_STATUSES:
                return _handle_terminal_status(runner, progress, wp_index, show_progress)
        time.sleep(0.1)


def _print_progress(
    runner: MissionRunner,
    progress: dict,
    wp_index: int,
    status: str | None,
    last_print_time: float,
    show_progress: bool,
) -> float:
    current_time = time.time()
    if status != "wayline_progress" or not show_progress or current_time - last_print_time < 1.0:
        return last_print_time
    callsign = runner.config.get("callsign", "UAV")
    console.print(
        f"[bright_cyan]→ [{callsign}] 飞向航点 {wp_index}: {_progress_info(progress)}[/bright_cyan]"
    )
    return current_time


def _progress_info(progress: dict) -> str:
    parts = []
    if progress.get("remaining_distance") is not None:
        parts.append(f"剩余距离: {progress['remaining_distance']:.1f}m")
    if progress.get("remaining_time") is not None:
        parts.append(f"剩余时间: {progress['remaining_time']:.1f}s")
    if progress.get("way_point_index") is not None:
        parts.append(f"航点索引: {progress['way_point_index']}")
    return " | ".join(parts) if parts else "飞行中..."


def _handle_terminal_status(
    runner: MissionRunner, progress: dict, wp_index: int, show_progress: bool
) -> bool:
    if not show_progress:
        return progress.get("status") == "wayline_ok"
    callsign = runner.config.get("callsign", "UAV")
    status = progress.get("status")
    if status == "wayline_ok":
        console.print(
            f"[bold bright_green]✓ [{callsign}] 已到达航点 {wp_index}！[/bold bright_green]"
        )
        return True
    color = "bright_red" if status == "wayline_failed" else "bright_yellow"
    label = "失败" if status == "wayline_failed" else "取消"
    console.print(f"[bold {color}]✗ [{callsign}] 飞向航点 {wp_index} {label}[/bold {color}]")
    console.print(f"[dim]   result_code: {progress.get('result')}[/dim]")
    return False

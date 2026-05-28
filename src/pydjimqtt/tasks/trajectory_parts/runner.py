from __future__ import annotations

from typing import Any

from rich.console import Console

from ...services import fly_to_point
from ..runner import MissionRunner
from .hover import hover_between_waypoints
from .monitor import monitor_runner_waypoint
from .state import update_mission_state_file

console = Console()


def fly_trajectory_sequence(
    runners: list[MissionRunner],
    waypoints: list[dict[str, Any]],
    height: float,
    max_speed: int = 12,
    hover_between_waypoints: float = 5.0,
    show_progress: bool = True,
    debug: bool = False,
) -> bool:
    """依次飞向多个航点（所有无人机并行执行相同轨迹）。"""
    total_waypoints = len(waypoints)
    all_success = True

    for wp_index, waypoint in enumerate(waypoints, 1):
        if _should_abort(runners):
            _mark_all(runners, wp_index - 1, "已取消")
            return False
        _start_waypoint(runners, waypoint, wp_index, total_waypoints, height, show_progress)
        fly_to_ids = _dispatch_waypoint(
            runners, waypoint, wp_index, total_waypoints, height, max_speed, show_progress
        )
        if fly_to_ids is None:
            return False
        if show_progress:
            console.print("[dim]监控飞行进度（实时显示）...[/dim]\n")
        all_success = (
            _monitor_waypoint(runners, fly_to_ids, wp_index, show_progress, debug) and all_success
        )
        if show_progress:
            console.print(
                f"[bold bright_green]✓ 航点 {wp_index}/{total_waypoints} 飞行完成[/bold bright_green]"
            )
        if not _hover_after_waypoint(
            runners, fly_to_ids, wp_index, total_waypoints, hover_between_waypoints, show_progress
        ):
            return False

    final_status = f"完成 ({total_waypoints}航点)" if all_success else "任务失败"
    _mark_all(runners, total_waypoints, final_status)
    return all_success


def _start_waypoint(runners, waypoint, wp_index, total_waypoints, height, show_progress) -> None:
    for runner in runners:
        runner.data["current_waypoint"] = wp_index
        update_mission_state_file(runner, wp_index, "飞行中")
    if show_progress:
        wp_id = waypoint.get("id", wp_index)
        console.print(
            f"\n[bold bright_cyan]━━━ 航点 {wp_index}/{total_waypoints} (ID: {wp_id}) ━━━[/bold bright_cyan]"
        )
        console.print(
            f"[bright_yellow]目标: lat={waypoint['lat']:.7f}, lon={waypoint['lon']:.7f}, h={height:.1f}m[/bright_yellow]"
        )


def _dispatch_waypoint(
    runners, waypoint, wp_index, total_waypoints, height, max_speed, show_progress
) -> dict[str, str] | None:
    fly_to_ids: dict[str, str] = {}
    for runner in runners:
        if _should_abort(runners):
            _mark_all(runners, wp_index - 1, "已取消")
            return None
        callsign = runner.config.get("callsign", "UAV")
        if show_progress:
            console.print(f"[bright_cyan][{callsign}] 飞向航点 {wp_index}...[/bright_cyan]")
        try:
            fly_to_ids[callsign] = fly_to_point(
                runner.caller,
                latitude=waypoint["lat"],
                longitude=waypoint["lon"],
                height=height,
                max_speed=max_speed,
            )
        except Exception as exc:
            _print_dispatch_failure(callsign, wp_index, total_waypoints, exc)
            _mark_all(runners, wp_index, f"失败(航点{wp_index})")
            return None
    return fly_to_ids


def _monitor_waypoint(runners, fly_to_ids, wp_index, show_progress, debug) -> bool:
    success = True
    for runner in runners:
        callsign = runner.config.get("callsign", "UAV")
        if callsign not in fly_to_ids:
            if show_progress:
                console.print(f"[dim][{callsign}] 跳过监控（service call 失败）[/dim]")
            continue
        success = (
            monitor_runner_waypoint(runner, fly_to_ids[callsign], wp_index, show_progress, debug)
            and success
        )
    return success


def _hover_after_waypoint(
    runners, fly_to_ids, wp_index, total_waypoints, hover_seconds, show_progress
) -> bool:
    if wp_index >= total_waypoints or hover_seconds <= 0:
        return True
    if _should_abort(runners):
        _mark_all(runners, wp_index, "已取消")
        return False
    hover_between_waypoints(runners, fly_to_ids, wp_index, hover_seconds, show_progress)
    return True


def _should_abort(runners) -> bool:
    return any(not runner.running for runner in runners)


def _mark_all(runners, wp_index: int, status: str) -> None:
    for runner in runners:
        update_mission_state_file(runner, wp_index, status)


def _print_dispatch_failure(
    callsign: str, wp_index: int, total_waypoints: int, exc: Exception
) -> None:
    console.print(
        f"\n[bold bright_red]✗ [{callsign}] Fly-to service 调用失败，终止轨迹任务[/bold bright_red]"
    )
    console.print(f"[yellow]   航点: {wp_index}/{total_waypoints}[/yellow]")
    console.print(f"[yellow]   异常: {exc}[/yellow]")

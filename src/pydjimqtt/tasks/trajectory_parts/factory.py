from __future__ import annotations

from typing import Any

from ..runner import MissionRunner
from .runner import fly_trajectory_sequence


def create_trajectory_mission(
    waypoints: list[dict[str, Any]],
    height: float,
    max_speed: int = 12,
    hover_between_waypoints: float = 5.0,
    show_progress: bool = True,
    debug: bool = False,
):
    """创建轨迹飞行任务函数（用于 run_parallel_missions）。"""

    def trajectory_mission(runner: MissionRunner):
        success = fly_trajectory_sequence(
            runners=[runner],
            waypoints=waypoints,
            height=height,
            max_speed=max_speed,
            hover_between_waypoints=hover_between_waypoints,
            show_progress=show_progress,
            debug=debug,
        )
        if not success:
            raise RuntimeError("轨迹飞行任务执行失败")

    return trajectory_mission

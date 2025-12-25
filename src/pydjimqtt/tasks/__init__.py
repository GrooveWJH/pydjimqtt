"""
任务模板 - 可复用的高级任务封装

这些模块提供任务执行框架和常用任务模板。
"""
from .runner import MissionRunner, run_parallel_missions, cleanup_missions
from .takeoff import create_takeoff_mission
from .trajectory import (
    load_trajectory,
    fly_trajectory_sequence,
    create_trajectory_mission
)
from .display import create_takeoff_table, create_trajectory_table

__all__ = [
    'MissionRunner',
    'run_parallel_missions',
    'cleanup_missions',
    'create_takeoff_mission',
    'load_trajectory',
    'fly_trajectory_sequence',
    'create_trajectory_mission',
    'create_takeoff_table',
    'create_trajectory_table',
]

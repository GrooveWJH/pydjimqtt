from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_trajectory(filepath: str) -> list[dict[str, Any]]:
    """从 JSON 文件加载航点数据。"""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"航点文件不存在: {filepath}")

    with open(path, encoding="utf-8") as trajectory_file:
        waypoints = json.load(trajectory_file)

    if not isinstance(waypoints, list) or len(waypoints) == 0:
        raise ValueError(f"航点数据格式错误或为空: {filepath}")

    for index, waypoint in enumerate(waypoints):
        if not isinstance(waypoint, dict):
            raise ValueError(f"航点 {index + 1} 数据格式错误: {waypoint}")
        if "lat" not in waypoint or "lon" not in waypoint:
            raise ValueError(f"航点 {index + 1} 缺少 lat 或 lon 字段: {waypoint}")
    return waypoints

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

from ..runner import MissionRunner

MISSION_STATE_FILE = Path("/tmp/pydjimqtt_mission_state.json")


def update_mission_state_file(runner: MissionRunner, wp_index: int, task_status: str):
    """更新任务状态文件（原子写入，进程安全）。"""
    try:
        callsign = runner.config.get("callsign", "UAV")
        mission_state = {}
        if MISSION_STATE_FILE.exists():
            with open(MISSION_STATE_FILE) as state_file:
                mission_state = json.load(state_file)

        mission_state[callsign] = {
            "current_waypoint": wp_index,
            "total_waypoints": runner.data.get("total_waypoints", 0),
            "task_status": task_status,
            "timestamp": time.time(),
            "trajectory_file": runner.config.get("trajectory_file", ""),
        }
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, dir="/tmp", prefix="pydjimqtt_mission_"
        ) as tmp_file:
            json.dump(mission_state, tmp_file, indent=2)
            tmp_path = tmp_file.name
        shutil.move(tmp_path, MISSION_STATE_FILE)
    except Exception:
        pass

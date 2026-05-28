#!/usr/bin/env python3
"""Multi-drone camera control compatibility entrypoint."""

import os
import sys

tool_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, tool_dir)
sys.path.insert(0, os.path.dirname(tool_dir))

from camera_allinone_cli import (  # noqa: E402
    MQTT_CONFIG,
    UAV_CONFIGS,
    aim_down_loop,
    getch,
    gimbal_center,
    gimbal_down,
    keyboard_loop,
    log,
    lookat_ground,
    lookdown_loop,
    main,
    parallel_run,
    status_loop,
    toggle_aim_down,
    toggle_camera_type,
    toggle_lookdown,
    zoom_in,
    zoom_out,
)
from camera_allinone_cli import state as _state  # noqa: E402

uav_states = _state.uav_states
executor = _state.executor
print_lock = _state.print_lock

__all__ = [
    "MQTT_CONFIG",
    "UAV_CONFIGS",
    "aim_down_loop",
    "executor",
    "getch",
    "gimbal_center",
    "gimbal_down",
    "keyboard_loop",
    "log",
    "lookat_ground",
    "lookdown_loop",
    "main",
    "parallel_run",
    "print_lock",
    "status_loop",
    "toggle_aim_down",
    "toggle_camera_type",
    "toggle_lookdown",
    "uav_states",
    "zoom_in",
    "zoom_out",
]


def __getattr__(name: str):
    if name in {"stop_flag", "lookdown_lock", "aim_down_lock"}:
        return getattr(_state, name)
    raise AttributeError(name)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"异常: {exc}")
        import traceback

        traceback.print_exc()

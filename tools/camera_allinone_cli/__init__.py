"""Multi-drone camera all-in-one CLI package."""

from .actions import (
    gimbal_center,
    gimbal_down,
    lookat_ground,
    toggle_camera_type,
    zoom_in,
    zoom_out,
)
from .config import MQTT_CONFIG, UAV_CONFIGS
from .keyboard import getch, keyboard_loop
from .loops import aim_down_loop, lookdown_loop, status_loop, toggle_aim_down, toggle_lookdown
from .runtime import main
from .state import log, parallel_run

__all__ = [
    "MQTT_CONFIG",
    "UAV_CONFIGS",
    "aim_down_loop",
    "getch",
    "gimbal_center",
    "gimbal_down",
    "keyboard_loop",
    "log",
    "lookat_ground",
    "lookdown_loop",
    "main",
    "parallel_run",
    "status_loop",
    "toggle_aim_down",
    "toggle_camera_type",
    "toggle_lookdown",
    "zoom_in",
    "zoom_out",
]

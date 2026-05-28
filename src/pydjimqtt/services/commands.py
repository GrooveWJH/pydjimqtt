"""Compatibility exports for DJI service commands."""

from .common import call_service as _call_service
from .common import publish_drc_down as _publish_drc_down
from .cloud.control_auth import request_control_auth, release_control_auth
from .cloud.drc_setup import setup_drc_connection, setup_multiple_drc_connections
from .cloud.flight import fly_to_point, return_home, send_stick_control
from .cloud.gimbal_reset import reset_gimbal
from .cloud.live import (
    change_live_lens,
    enter_drc_mode,
    exit_drc_mode,
    set_live_quality,
    start_live_push,
    stop_live_push,
)

__all__ = [
    "_call_service",
    "_publish_drc_down",
    "request_control_auth",
    "release_control_auth",
    "enter_drc_mode",
    "exit_drc_mode",
    "change_live_lens",
    "set_live_quality",
    "start_live_push",
    "stop_live_push",
    "return_home",
    "fly_to_point",
    "send_stick_control",
    "setup_drc_connection",
    "setup_multiple_drc_connections",
    "reset_gimbal",
]

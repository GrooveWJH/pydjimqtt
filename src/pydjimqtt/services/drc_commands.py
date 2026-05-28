"""Compatibility exports for DRC downlink commands."""

from .drc import (
    _next_seq,
    _publish_drc_down,
    _wait_for_drc_reply,
    camera_aim,
    camera_look_at,
    camera_screen_split,
    camera_screen_split_wait,
    drc_live_lens_change,
    drc_live_lens_change_wait,
    drone_emergency_stop,
    drone_emergency_stop_wait,
    send_stick_control,
    set_camera_zoom,
    take_photo,
)
from .drc.photo import take_photo_wait as _take_photo_wait


def take_photo_wait(*args, **kwargs):
    kwargs.setdefault("send_photo", take_photo)
    return _take_photo_wait(*args, **kwargs)


__all__ = [
    "_next_seq",
    "_publish_drc_down",
    "_wait_for_drc_reply",
    "send_stick_control",
    "set_camera_zoom",
    "camera_screen_split",
    "camera_screen_split_wait",
    "drc_live_lens_change",
    "drc_live_lens_change_wait",
    "take_photo",
    "take_photo_wait",
    "camera_look_at",
    "camera_aim",
    "drone_emergency_stop",
    "drone_emergency_stop_wait",
]

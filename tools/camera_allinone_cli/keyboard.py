"""Terminal keyboard input handling."""

import sys
import termios
import tty

from . import state
from .actions import (
    gimbal_center,
    gimbal_down,
    lookat_ground,
    toggle_camera_type,
    zoom_in,
    zoom_out,
)
from .loops import toggle_aim_down, toggle_lookdown


def getch() -> str:
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def keyboard_loop() -> None:
    key_map = {
        "\x1b[A": gimbal_center,
        "\x1b[B": gimbal_down,
        "p": lookat_ground,
        "z": zoom_in,
        "x": zoom_out,
        "l": toggle_lookdown,
        "w": toggle_camera_type,
        "a": toggle_aim_down,
    }

    while not state.stop_flag:
        try:
            ch = _read_key()
            if ch in ("q", "\x03"):
                state.log(">>> 退出")
                state.stop_flag = True
                break
            if ch in key_map:
                key_map[ch]()
        except Exception:
            pass


def _read_key() -> str:
    ch = getch()
    if ch != "\x1b":
        return ch
    ch2 = getch()
    if ch2 == "[":
        return "\x1b[" + getch()
    return ch

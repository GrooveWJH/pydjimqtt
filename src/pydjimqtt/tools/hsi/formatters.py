"""Formatting and coordinate helpers for HSI obstacle views."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from .models import NO_OBSTACLE_MM


def to_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def fmt_ts(ts_ms: int | None) -> str:
    if ts_ms is None:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000.0)
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    except Exception:
        return str(ts_ms)


def fmt_mm(mm: int | None) -> str:
    if mm is None:
        return "N/A"
    if mm >= NO_OBSTACLE_MM:
        return ">=60m"
    return f"{mm / 1000:.2f}m"


def fmt_enable_work(enable: bool | None, work: bool | None) -> str:
    if enable is None and work is None:
        return "N/A"
    e = "on" if enable else "off"
    w = "work" if work else "idle"
    return f"{e}/{w}"


def polar_to_canvas(
    cx: float, cy: float, radius: float, deg_cw_from_front: float
) -> tuple[float, float]:
    rad = math.radians(deg_cw_from_front)
    x = cx + radius * math.sin(rad)
    y = cy - radius * math.cos(rad)
    return x, y


_to_int = to_int
_to_bool = to_bool
_fmt_ts = fmt_ts
_fmt_mm = fmt_mm
_fmt_enable_work = fmt_enable_work
_polar_to_canvas = polar_to_canvas

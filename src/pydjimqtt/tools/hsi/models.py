"""Models and constants for the HSI obstacle viewer."""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_GATEWAY_SN = "9N9CN2B00121JN"
DEFAULT_HOST = "192.168.11.100"
DEFAULT_PORT = 1883

NO_OBSTACLE_MM = 60000
MAX_PLOT_MM = 12000


@dataclass
class HsiFrame:
    ts_ms: int | None = None
    seq: int | None = None
    around_distances_mm: list[int] = field(default_factory=list)
    up_distance_mm: int | None = None
    down_distance_mm: int | None = None
    up_enable: bool | None = None
    up_work: bool | None = None
    down_enable: bool | None = None
    down_work: bool | None = None
    left_enable: bool | None = None
    left_work: bool | None = None
    right_enable: bool | None = None
    right_work: bool | None = None
    front_enable: bool | None = None
    front_work: bool | None = None
    back_enable: bool | None = None
    back_work: bool | None = None
    vertical_enable: bool | None = None
    vertical_work: bool | None = None
    horizontal_enable: bool | None = None
    horizontal_work: bool | None = None

#!/usr/bin/env python3
"""DRC HSI obstacle viewer compatibility entrypoint."""

from __future__ import annotations

from .hsi import (
    DEFAULT_GATEWAY_SN,
    DEFAULT_HOST,
    DEFAULT_PORT,
    MAX_PLOT_MM,
    NO_OBSTACLE_MM,
    HsiFrame,
    HsiMqttClient,
    _fmt_enable_work,
    _fmt_mm,
    _fmt_ts,
    _polar_to_canvas,
    _to_bool,
    _to_int,
    main,
    parse_args,
    run_mpl_viewer,
    run_tk_viewer,
)

__all__ = [
    "DEFAULT_GATEWAY_SN",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "HsiFrame",
    "HsiMqttClient",
    "MAX_PLOT_MM",
    "NO_OBSTACLE_MM",
    "_fmt_enable_work",
    "_fmt_mm",
    "_fmt_ts",
    "_polar_to_canvas",
    "_to_bool",
    "_to_int",
    "main",
    "parse_args",
    "run_mpl_viewer",
    "run_tk_viewer",
]


if __name__ == "__main__":
    main()

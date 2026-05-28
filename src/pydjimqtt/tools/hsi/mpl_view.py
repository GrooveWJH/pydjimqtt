"""Matplotlib HSI obstacle map view."""

from __future__ import annotations

import math
import queue
import time
from typing import Any, cast

from .client import HsiMqttClient
from .formatters import fmt_mm, fmt_ts
from .models import HsiFrame, NO_OBSTACLE_MM


def run_mpl_viewer(
    mqtt_client: HsiMqttClient, msg_queue: queue.Queue[HsiFrame], max_plot_mm: int
) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    state = {"frame": HsiFrame(), "last_msg_monotonic": 0.0}
    fig = plt.figure("DRC 避障地图 (hsi_info_push)", figsize=(10, 8))
    ax = cast(Any, fig.add_subplot(111, projection="polar"))
    _setup_axis(fig, ax, max_plot_mm)

    info = fig.text(0.02, 0.96, "MQTT: connecting...", color="#d8e7ef", fontsize=10)
    info2 = fig.text(0.02, 0.93, "等待 hsi_info_push...", color="#9eb4bf", fontsize=9)

    def update(_frame_idx: int):
        changed = _drain_queue(msg_queue, state)
        _update_info(info, info2, mqtt_client, state)
        if changed:
            _redraw(ax, state["frame"], max_plot_mm)
        return (info, info2)

    fig.canvas.mpl_connect("close_event", lambda _event: mqtt_client.stop())
    mqtt_client.start()
    _redraw(ax, state["frame"], max_plot_mm)
    _ani = FuncAnimation(fig, update, interval=180, blit=False, cache_frame_data=False)
    plt.show()


def _setup_axis(fig, ax, max_plot_mm: int) -> None:
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, max_plot_mm / 1000.0)
    ax.set_facecolor("#101417")
    fig.patch.set_facecolor("#101417")


def _drain_queue(msg_queue: queue.Queue[HsiFrame], state: dict) -> bool:
    changed = False
    while True:
        try:
            state["frame"] = msg_queue.get_nowait()
        except queue.Empty:
            return changed
        state["last_msg_monotonic"] = time.monotonic()
        changed = True


def _update_info(info, info2, mqtt_client: HsiMqttClient, state: dict) -> None:
    frame = state["frame"]
    age = state["last_msg_monotonic"]
    stale = "N/A" if age <= 0 else f"{time.monotonic() - age:.1f}s"
    online = "connected" if mqtt_client.connected else "disconnected"
    info.set_text(f"MQTT: {online} | topic: {mqtt_client.topic} | last_msg_age: {stale}")
    info2.set_text(
        "seq={} ts={} up/down={}/{} around_points={}".format(
            frame.seq,
            fmt_ts(frame.ts_ms),
            fmt_mm(frame.up_distance_mm),
            fmt_mm(frame.down_distance_mm),
            len(frame.around_distances_mm),
        )
    )


def _redraw(ax, frame: HsiFrame, max_plot_mm: int) -> None:
    ax.clear()
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, max_plot_mm / 1000.0)
    ax.set_facecolor("#101417")
    ax.grid(color="#2c3a40")
    ax.tick_params(colors="#9eb4bf")
    ax.set_title("around_distances 极坐标图（0°=前方，顺时针）", color="#d8e7ef", pad=16)

    points = frame.around_distances_mm
    if not points:
        return

    theta = [(2.0 * math.pi * i) / len(points) for i in range(len(points))]
    radius = [min(max(0, int(mm)), max_plot_mm) / 1000.0 for mm in points]
    ax.scatter(theta, radius, c=[_point_color(mm) for mm in points], s=7)
    ax.plot(theta + [theta[0]], radius + [radius[0]], color="#4ecbff", linewidth=1)


def _point_color(mm: int) -> str:
    valid_mm = max(0, int(mm))
    if valid_mm >= NO_OBSTACLE_MM:
        return "#3b4c54"
    if valid_mm < 2000:
        return "#ff5f57"
    if valid_mm < 5000:
        return "#ffb454"
    return "#6ad1ff"

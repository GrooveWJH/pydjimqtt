"""Tkinter HSI obstacle map view."""

from __future__ import annotations

import queue
import time

from .client import HsiMqttClient
from .formatters import fmt_enable_work, fmt_mm, fmt_ts, polar_to_canvas
from .models import HsiFrame, NO_OBSTACLE_MM


def run_tk_viewer(
    mqtt_client: HsiMqttClient, msg_queue: queue.Queue[HsiFrame], max_plot_mm: int
) -> None:
    import tkinter as tk
    from tkinter import ttk

    state = {"frame": HsiFrame(), "last_msg_monotonic": 0.0}
    root = tk.Tk()
    root.title("DRC 避障地图 (hsi_info_push)")
    root.geometry("980x760")

    main = ttk.Frame(root, padding=10)
    main.pack(fill=tk.BOTH, expand=True)
    top = ttk.Frame(main)
    top.pack(fill=tk.X)

    status_var = tk.StringVar(value="MQTT: connecting...")
    meta_var = tk.StringVar(value="等待 hsi_info_push...")
    dist_var = tk.StringVar(value="up/down: N/A")
    switch_var = tk.StringVar(value="front/back/left/right/up/down: N/A")
    for var, font in ((status_var, ("Helvetica", 12, "bold")), (meta_var, None)):
        ttk.Label(top, textvariable=var, font=font).pack(anchor="w")
    ttk.Label(top, textvariable=dist_var).pack(anchor="w")
    ttk.Label(top, textvariable=switch_var).pack(anchor="w")

    canvas = tk.Canvas(main, bg="#101417", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    def update_meta(frame: HsiFrame) -> None:
        meta_var.set(
            f"method=hsi_info_push seq={frame.seq} ts={fmt_ts(frame.ts_ms)} "
            f"around_points={len(frame.around_distances_mm)}"
        )
        dist_var.set(f"up/down: {fmt_mm(frame.up_distance_mm)} / {fmt_mm(frame.down_distance_mm)}")
        switch_var.set(
            "front/back/left/right/up/down: "
            f"{fmt_enable_work(frame.front_enable, frame.front_work)} / "
            f"{fmt_enable_work(frame.back_enable, frame.back_work)} / "
            f"{fmt_enable_work(frame.left_enable, frame.left_work)} / "
            f"{fmt_enable_work(frame.right_enable, frame.right_work)} / "
            f"{fmt_enable_work(frame.up_enable, frame.up_work)} / "
            f"{fmt_enable_work(frame.down_enable, frame.down_work)}"
        )

    def redraw(frame: HsiFrame) -> None:
        _draw_canvas(canvas, frame, max_plot_mm)

    def poll_loop() -> None:
        changed = _drain_queue(msg_queue, state)
        age = state["last_msg_monotonic"]
        stale = "N/A" if age <= 0 else f"{time.monotonic() - age:.1f}s"
        online = "connected" if mqtt_client.connected else "disconnected"
        status_var.set(f"MQTT: {online} | topic: {mqtt_client.topic} | last_msg_age: {stale}")

        if changed:
            update_meta(state["frame"])
            redraw(state["frame"])
        root.after(120, poll_loop)

    def on_close() -> None:
        mqtt_client.stop()
        root.destroy()

    canvas.bind("<Configure>", lambda _e: redraw(state["frame"]))
    root.protocol("WM_DELETE_WINDOW", on_close)
    mqtt_client.start()
    update_meta(state["frame"])
    redraw(state["frame"])
    root.after(120, poll_loop)
    root.mainloop()


def _drain_queue(msg_queue: queue.Queue[HsiFrame], state: dict) -> bool:
    changed = False
    while True:
        try:
            state["frame"] = msg_queue.get_nowait()
        except queue.Empty:
            return changed
        state["last_msg_monotonic"] = time.monotonic()
        changed = True


def _draw_canvas(canvas, frame: HsiFrame, max_plot_mm: int) -> None:
    canvas.delete("all")
    width = max(1, int(canvas.winfo_width()))
    height = max(1, int(canvas.winfo_height()))
    cx, cy = width / 2.0, height / 2.0
    r_max = min(width, height) * 0.40

    _draw_grid(canvas, cx, cy, r_max, max_plot_mm)
    _draw_points(canvas, frame, cx, cy, r_max, max_plot_mm)


def _draw_grid(canvas, cx: float, cy: float, r_max: float, max_plot_mm: int) -> None:
    for meters in (2, 4, 6, 8, 10, 12):
        rr = r_max * min((meters * 1000) / max_plot_mm, 1.0)
        canvas.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline="#2c3a40")
        canvas.create_text(
            cx + 4,
            cy - rr - 4,
            text=f"{meters}m",
            anchor="w",
            fill="#7d8f9a",
            font=("Helvetica", 9),
        )

    for deg, label in ((0, "F"), (90, "R"), (180, "B"), (270, "L")):
        x, y = polar_to_canvas(cx, cy, r_max, deg)
        canvas.create_line(cx, cy, x, y, fill="#253138")
        lx, ly = polar_to_canvas(cx, cy, r_max + 16, deg)
        canvas.create_text(lx, ly, text=label, fill="#9cb0bc", font=("Helvetica", 10, "bold"))

    canvas.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill="#5ec8ff", outline="")


def _draw_points(
    canvas, frame: HsiFrame, cx: float, cy: float, r_max: float, max_plot_mm: int
) -> None:
    points = frame.around_distances_mm
    if not points:
        canvas.create_text(
            cx, cy, text="暂无 around_distances 数据", fill="#8ea3b0", font=("Helvetica", 14)
        )
        return

    poly_xy: list[float] = []
    for i, mm in enumerate(points):
        x, y = _point_xy(cx, cy, r_max, max_plot_mm, len(points), i, mm)
        canvas.create_oval(x - 1.7, y - 1.7, x + 1.7, y + 1.7, fill=_point_color(mm), outline="")
        poly_xy.extend((x, y))

    if len(poly_xy) >= 6:
        canvas.create_polygon(*poly_xy, outline="#4ecbff", fill="", width=1)


def _point_xy(
    cx: float, cy: float, r_max: float, max_plot_mm: int, count: int, index: int, mm: int
) -> tuple[float, float]:
    deg = (index * 360.0) / count
    clipped_mm = min(max(0, int(mm)), max_plot_mm)
    return polar_to_canvas(cx, cy, r_max * (clipped_mm / max_plot_mm), deg)


def _point_color(mm: int) -> str:
    valid_mm = max(0, int(mm))
    if valid_mm >= NO_OBSTACLE_MM:
        return "#3b4c54"
    if valid_mm < 2000:
        return "#ff5f57"
    if valid_mm < 5000:
        return "#ffb454"
    return "#6ad1ff"

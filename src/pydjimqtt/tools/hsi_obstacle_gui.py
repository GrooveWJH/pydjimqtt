#!/usr/bin/env python3
"""DRC HSI obstacle viewer GUI.

Subscribe to `thing/product/{gateway_sn}/drc/up`, parse `hsi_info_push`,
and render `around_distances` as a polar obstacle map.

Direction convention used by this tool:
- around_distances[0] is treated as FRONT (0 deg)
- index increases clockwise
"""

from __future__ import annotations

import argparse
import json
import math
import queue
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

try:
    import paho.mqtt.client as mqtt
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"paho-mqtt not available: {exc}")


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


class HsiMqttClient:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        topic: str,
        username: str,
        password: str,
        out_queue: queue.Queue[HsiFrame],
    ) -> None:
        self.host = host
        self.port = port
        self.topic = topic
        self._queue = out_queue

        self._client = mqtt.Client()
        if username:
            self._client.username_pw_set(username, password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self.connected = False
        self.last_disconnect_rc: int | None = None

    def start(self) -> None:
        self._client.connect(self.host, self.port, keepalive=60)
        self._client.loop_start()

    def stop(self) -> None:
        try:
            self._client.loop_stop()
        finally:
            try:
                self._client.disconnect()
            except Exception:
                pass

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, rc: int) -> None:
        self.connected = rc == 0
        if rc == 0:
            client.subscribe(self.topic, qos=0)
            print(f"[MQTT] connected rc={rc}, subscribed: {self.topic}")
        else:
            print(f"[MQTT] connect failed rc={rc}")

    def _on_disconnect(self, _client: mqtt.Client, _userdata: Any, rc: int) -> None:
        self.connected = False
        self.last_disconnect_rc = rc
        print(f"[MQTT] disconnected rc={rc}")

    def _on_message(self, _client: mqtt.Client, _userdata: Any, msg: Any) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8", errors="ignore"))
        except Exception:
            return

        method = str(payload.get("method") or "")
        if method != "hsi_info_push":
            return

        data = payload.get("data")
        if not isinstance(data, dict):
            return

        around = data.get("around_distances")
        if isinstance(around, list):
            around_list = []
            for item in around:
                parsed = _to_int(item)
                if parsed is not None:
                    around_list.append(parsed)
        else:
            around_list = []

        frame = HsiFrame(
            ts_ms=_to_int(payload.get("timestamp")),
            seq=_to_int(payload.get("seq")),
            around_distances_mm=around_list,
            up_distance_mm=_to_int(data.get("up_distance")),
            down_distance_mm=_to_int(data.get("down_distance")),
            up_enable=_to_bool(data.get("up_enable")),
            up_work=_to_bool(data.get("up_work")),
            down_enable=_to_bool(data.get("down_enable")),
            down_work=_to_bool(data.get("down_work")),
            left_enable=_to_bool(data.get("left_enable")),
            left_work=_to_bool(data.get("left_work")),
            right_enable=_to_bool(data.get("right_enable")),
            right_work=_to_bool(data.get("right_work")),
            front_enable=_to_bool(data.get("front_enable")),
            front_work=_to_bool(data.get("front_work")),
            back_enable=_to_bool(data.get("back_enable")),
            back_work=_to_bool(data.get("back_work")),
            vertical_enable=_to_bool(data.get("vertical_enable")),
            vertical_work=_to_bool(data.get("vertical_work")),
            horizontal_enable=_to_bool(data.get("horizontal_enable")),
            horizontal_work=_to_bool(data.get("horizontal_work")),
        )

        try:
            self._queue.put_nowait(frame)
        except queue.Full:
            try:
                _ = self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(frame)
            except queue.Full:
                pass


def run_tk_viewer(mqtt_client: HsiMqttClient, msg_queue: queue.Queue[HsiFrame], max_plot_mm: int) -> None:
    import tkinter as tk
    from tkinter import ttk

    last_frame = HsiFrame()
    last_msg_monotonic = 0.0

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

    ttk.Label(top, textvariable=status_var, font=("Helvetica", 12, "bold")).pack(anchor="w")
    ttk.Label(top, textvariable=meta_var).pack(anchor="w")
    ttk.Label(top, textvariable=dist_var).pack(anchor="w")
    ttk.Label(top, textvariable=switch_var).pack(anchor="w")

    canvas = tk.Canvas(main, bg="#101417", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    def update_meta(frame: HsiFrame) -> None:
        ts_text = _fmt_ts(frame.ts_ms)
        points = len(frame.around_distances_mm)
        meta_var.set(f"method=hsi_info_push seq={frame.seq} ts={ts_text} around_points={points}")
        dist_var.set(f"up/down: {_fmt_mm(frame.up_distance_mm)} / {_fmt_mm(frame.down_distance_mm)}")
        switch_var.set(
            "front/back/left/right/up/down: "
            f"{_fmt_enable_work(frame.front_enable, frame.front_work)} / "
            f"{_fmt_enable_work(frame.back_enable, frame.back_work)} / "
            f"{_fmt_enable_work(frame.left_enable, frame.left_work)} / "
            f"{_fmt_enable_work(frame.right_enable, frame.right_work)} / "
            f"{_fmt_enable_work(frame.up_enable, frame.up_work)} / "
            f"{_fmt_enable_work(frame.down_enable, frame.down_work)}"
        )

    def redraw(frame: HsiFrame) -> None:
        c = canvas
        c.delete("all")

        w = max(1, int(c.winfo_width()))
        h = max(1, int(c.winfo_height()))
        cx, cy = w / 2.0, h / 2.0
        r_max = min(w, h) * 0.40

        for m in (2, 4, 6, 8, 10, 12):
            rr = r_max * min((m * 1000) / max_plot_mm, 1.0)
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline="#2c3a40")
            c.create_text(cx + 4, cy - rr - 4, text=f"{m}m", anchor="w", fill="#7d8f9a", font=("Helvetica", 9))

        for deg, label in ((0, "F"), (90, "R"), (180, "B"), (270, "L")):
            x, y = _polar_to_canvas(cx, cy, r_max, deg)
            c.create_line(cx, cy, x, y, fill="#253138")
            lx, ly = _polar_to_canvas(cx, cy, r_max + 16, deg)
            c.create_text(lx, ly, text=label, fill="#9cb0bc", font=("Helvetica", 10, "bold"))

        c.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill="#5ec8ff", outline="")

        points = frame.around_distances_mm
        if not points:
            c.create_text(cx, cy, text="暂无 around_distances 数据", fill="#8ea3b0", font=("Helvetica", 14))
            return

        n = len(points)
        poly_xy: list[float] = []
        for i, mm in enumerate(points):
            deg = (i * 360.0) / n
            valid_mm = max(0, int(mm))
            clipped_mm = min(valid_mm, max_plot_mm)
            radius = r_max * (clipped_mm / max_plot_mm)
            x, y = _polar_to_canvas(cx, cy, radius, deg)

            if valid_mm >= NO_OBSTACLE_MM:
                color = "#3b4c54"
            elif valid_mm < 2000:
                color = "#ff5f57"
            elif valid_mm < 5000:
                color = "#ffb454"
            else:
                color = "#6ad1ff"

            c.create_oval(x - 1.7, y - 1.7, x + 1.7, y + 1.7, fill=color, outline="")
            poly_xy.extend((x, y))

        if len(poly_xy) >= 6:
            c.create_polygon(*poly_xy, outline="#4ecbff", fill="", width=1)

    def poll_loop() -> None:
        nonlocal last_frame, last_msg_monotonic

        changed = False
        while True:
            try:
                frame = msg_queue.get_nowait()
            except queue.Empty:
                break
            last_frame = frame
            last_msg_monotonic = time.monotonic()
            changed = True

        online = "connected" if mqtt_client.connected else "disconnected"
        stale = "N/A" if last_msg_monotonic <= 0 else f"{time.monotonic() - last_msg_monotonic:.1f}s"
        status_var.set(f"MQTT: {online} | topic: {mqtt_client.topic} | last_msg_age: {stale}")

        if changed:
            update_meta(last_frame)
            redraw(last_frame)

        root.after(120, poll_loop)

    def on_close() -> None:
        mqtt_client.stop()
        root.destroy()

    canvas.bind("<Configure>", lambda _e: redraw(last_frame))
    root.protocol("WM_DELETE_WINDOW", on_close)

    mqtt_client.start()
    update_meta(last_frame)
    redraw(last_frame)
    root.after(120, poll_loop)
    root.mainloop()


def run_mpl_viewer(mqtt_client: HsiMqttClient, msg_queue: queue.Queue[HsiFrame], max_plot_mm: int) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    last_frame = HsiFrame()
    last_msg_monotonic = 0.0

    fig = plt.figure("DRC 避障地图 (hsi_info_push)", figsize=(10, 8))
    ax = fig.add_subplot(111, projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, max_plot_mm / 1000.0)
    ax.set_facecolor("#101417")
    fig.patch.set_facecolor("#101417")

    info = fig.text(0.02, 0.96, "MQTT: connecting...", color="#d8e7ef", fontsize=10)
    info2 = fig.text(0.02, 0.93, "等待 hsi_info_push...", color="#9eb4bf", fontsize=9)

    def redraw(frame: HsiFrame) -> None:
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

        n = len(points)
        theta = [(2.0 * math.pi * i) / n for i in range(n)]
        radius = [min(max(0, int(mm)), max_plot_mm) / 1000.0 for mm in points]

        colors = []
        for mm in points:
            valid_mm = max(0, int(mm))
            if valid_mm >= NO_OBSTACLE_MM:
                colors.append("#3b4c54")
            elif valid_mm < 2000:
                colors.append("#ff5f57")
            elif valid_mm < 5000:
                colors.append("#ffb454")
            else:
                colors.append("#6ad1ff")

        ax.scatter(theta, radius, c=colors, s=7)
        ax.plot(theta + [theta[0]], radius + [radius[0]], color="#4ecbff", linewidth=1)

    def update(_frame_idx: int):
        nonlocal last_frame, last_msg_monotonic

        changed = False
        while True:
            try:
                frame = msg_queue.get_nowait()
            except queue.Empty:
                break
            last_frame = frame
            last_msg_monotonic = time.monotonic()
            changed = True

        online = "connected" if mqtt_client.connected else "disconnected"
        stale = "N/A" if last_msg_monotonic <= 0 else f"{time.monotonic() - last_msg_monotonic:.1f}s"
        info.set_text(f"MQTT: {online} | topic: {mqtt_client.topic} | last_msg_age: {stale}")

        info2.set_text(
            "seq={} ts={} up/down={}/{} around_points={}".format(
                last_frame.seq,
                _fmt_ts(last_frame.ts_ms),
                _fmt_mm(last_frame.up_distance_mm),
                _fmt_mm(last_frame.down_distance_mm),
                len(last_frame.around_distances_mm),
            )
        )

        if changed:
            redraw(last_frame)
        return (info, info2)

    def on_close(_event: Any) -> None:
        mqtt_client.stop()

    fig.canvas.mpl_connect("close_event", on_close)

    mqtt_client.start()
    redraw(last_frame)
    _ani = FuncAnimation(fig, update, interval=180, blit=False, cache_frame_data=False)
    plt.show()


def _to_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _fmt_ts(ts_ms: int | None) -> str:
    if ts_ms is None:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000.0)
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    except Exception:
        return str(ts_ms)


def _fmt_mm(mm: int | None) -> str:
    if mm is None:
        return "N/A"
    if mm >= NO_OBSTACLE_MM:
        return ">=60m"
    return f"{mm/1000:.2f}m"


def _fmt_enable_work(enable: bool | None, work: bool | None) -> str:
    if enable is None and work is None:
        return "N/A"
    e = "on" if enable else "off"
    w = "work" if work else "idle"
    return f"{e}/{w}"


def _polar_to_canvas(cx: float, cy: float, radius: float, deg_cw_from_front: float) -> tuple[float, float]:
    rad = math.radians(deg_cw_from_front)
    x = cx + radius * math.sin(rad)
    y = cy - radius * math.cos(rad)
    return x, y


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DRC hsi_info_push obstacle map viewer")
    parser.add_argument("--gateway-sn", default=DEFAULT_GATEWAY_SN)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--username", default="")
    parser.add_argument("--password", default="")
    parser.add_argument("--max-plot-mm", type=int, default=MAX_PLOT_MM)
    parser.add_argument("--backend", choices=["auto", "tk", "mpl"], default="auto")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    topic = f"thing/product/{args.gateway_sn}/drc/up"
    frame_queue: queue.Queue[HsiFrame] = queue.Queue(maxsize=200)

    mqtt_client = HsiMqttClient(
        host=args.host,
        port=args.port,
        topic=topic,
        username=args.username,
        password=args.password,
        out_queue=frame_queue,
    )

    backend = args.backend
    if backend == "auto":
        try:
            import tkinter  # noqa: F401

            backend = "tk"
        except Exception:
            backend = "mpl"

    if backend == "tk":
        run_tk_viewer(mqtt_client, frame_queue, max(1000, args.max_plot_mm))
    else:
        run_mpl_viewer(mqtt_client, frame_queue, max(1000, args.max_plot_mm))


if __name__ == "__main__":
    main()

"""CLI entrypoint for the HSI obstacle viewer."""

from __future__ import annotations

import argparse
import queue

from .client import HsiMqttClient
from .models import DEFAULT_GATEWAY_SN, DEFAULT_HOST, DEFAULT_PORT, HsiFrame, MAX_PLOT_MM
from .mpl_view import run_mpl_viewer
from .tk_view import run_tk_viewer


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
    frame_queue: queue.Queue[HsiFrame] = queue.Queue(maxsize=200)
    mqtt_client = HsiMqttClient(
        host=args.host,
        port=args.port,
        topic=f"thing/product/{args.gateway_sn}/drc/up",
        username=args.username,
        password=args.password,
        out_queue=frame_queue,
    )
    backend = _resolve_backend(args.backend)
    if backend == "tk":
        run_tk_viewer(mqtt_client, frame_queue, max(1000, args.max_plot_mm))
    else:
        run_mpl_viewer(mqtt_client, frame_queue, max(1000, args.max_plot_mm))


def _resolve_backend(backend: str) -> str:
    if backend != "auto":
        return backend
    try:
        import tkinter  # noqa: F401

        return "tk"
    except Exception:
        return "mpl"

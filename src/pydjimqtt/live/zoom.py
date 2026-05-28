from __future__ import annotations

import threading
import time

from ..services.drc_commands import set_camera_zoom
from ..utils import get_key
from .common import console


def zoom_control_loop(mqtt_client, payload_index: str, camera_type: str = "zoom") -> bool:
    """键盘控制变焦循环。"""
    state = {"zoom": 1.0}
    zoom_step = 0.5
    min_zoom = 1.0
    max_zoom = 112.0 if camera_type != "ir" else 20.0
    _print_zoom_help(state["zoom"], min_zoom, max_zoom)

    stop_flag = threading.Event()
    listener_thread = threading.Thread(
        target=_keyboard_listener,
        args=(
            mqtt_client,
            payload_index,
            camera_type,
            state,
            zoom_step,
            min_zoom,
            max_zoom,
            stop_flag,
        ),
        daemon=True,
    )
    listener_thread.start()
    stop_flag.wait()
    listener_thread.join(timeout=1)
    return True


def _keyboard_listener(
    mqtt_client,
    payload_index: str,
    camera_type: str,
    state: dict[str, float],
    zoom_step: float,
    min_zoom: float,
    max_zoom: float,
    stop_flag: threading.Event,
) -> None:
    while not stop_flag.is_set():
        try:
            key = get_key()
            if key == "UP":
                _adjust_zoom(mqtt_client, payload_index, camera_type, state, zoom_step, max_zoom)
            elif key == "DOWN":
                _adjust_zoom(mqtt_client, payload_index, camera_type, state, -zoom_step, min_zoom)
            elif key in ["q", "Q", "ESC"]:
                console.print("\n[yellow]退出变焦控制模式[/yellow]")
                stop_flag.set()
        except Exception as exc:
            console.print(f"[red]键盘输入错误: {exc}[/red]")
            time.sleep(0.1)


def _adjust_zoom(
    mqtt_client,
    payload_index: str,
    camera_type: str,
    state: dict[str, float],
    delta: float,
    limit: float,
) -> None:
    old_zoom = state["zoom"]
    new_zoom = min(old_zoom + delta, limit) if delta > 0 else max(old_zoom + delta, limit)
    if new_zoom == old_zoom:
        console.print(f"[yellow]已达到{'最大' if delta > 0 else '最小'}变焦 ({limit}x)[/yellow]")
        return
    state["zoom"] = new_zoom
    marker = "↑" if delta > 0 else "↓"
    action = "放大至" if delta > 0 else "缩小至"
    console.print(f"[cyan]{marker}[/cyan] {action} [bold green]{new_zoom:.1f}x[/bold green]")
    set_camera_zoom(mqtt_client, payload_index, new_zoom, camera_type)


def _print_zoom_help(zoom_factor: float, min_zoom: float, max_zoom: float) -> None:
    console.print("\n[bold cyan]========== 变焦控制模式 ==========[/bold cyan]")
    console.print("[yellow]使用方向键控制变焦：[/yellow]")
    console.print("  [green]↑[/green] - 放大 (zoom in)")
    console.print("  [green]↓[/green] - 缩小 (zoom out)")
    console.print("  [red]q[/red] 或 [red]ESC[/red] - 退出并停止直播")
    console.print(f"\n[dim]当前变焦: {zoom_factor}x (范围: {min_zoom}-{max_zoom}x)[/dim]\n")

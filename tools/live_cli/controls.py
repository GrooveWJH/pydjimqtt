from __future__ import annotations

import select
import sys

from rich.console import Console

from pydjimqtt import change_live_lens, set_live_quality
from pydjimqtt.services.drc_commands import set_camera_zoom

from .config import QUALITY_NAMES, connections, live_states
from .status import display_live_status

console = Console()


def read_key_nonblocking():
    if sys.platform == "win32":
        import msvcrt

        if msvcrt.kbhit():
            return msvcrt.getch().decode("utf-8")
    else:
        readable, _writable, _errors = select.select([sys.stdin], [], [], 0)
        if readable:
            return sys.stdin.read(1)
    return None


def change_all_quality(new_quality):
    quality_name = QUALITY_NAMES.get(new_quality, "未知")
    console.print(f"\n[bold cyan]切换所有直播到质量 {new_quality} ({quality_name})[/bold cyan]")
    success_count, total_count = 0, 0
    for sn, state in live_states.items():
        if not state["video_id"]:
            continue
        total_count += 1
        conn = connections[sn]
        callsign = conn["config"]["callsign"]
        try:
            set_live_quality(conn["caller"], state["video_id"], new_quality)
            state["quality"] = new_quality
            success_count += 1
            console.print(f"  [green]✓ {callsign}[/green]")
        except Exception as exc:
            console.print(f"  [red]✗ {callsign}: {exc}[/red]")
    console.print(f"[green]完成: {success_count}/{total_count} 架无人机已切换[/green]\n")
    display_live_status()


def toggle_all_lens():
    console.print("\n[bold cyan]切换所有直播镜头[/bold cyan]")
    success_count, total_count = 0, 0
    for sn, state in live_states.items():
        if not state["video_id"]:
            continue
        total_count += 1
        conn = connections[sn]
        callsign = conn["config"]["callsign"]
        new_lens = "wide" if state["lens_type"] == "zoom" else "zoom"
        lens_name = "广角" if new_lens == "wide" else "变焦"
        try:
            change_live_lens(conn["caller"], state["video_id"], new_lens)
            state["lens_type"] = new_lens
            success_count += 1
            console.print(f"  [green]✓ {callsign}: {lens_name}[/green]")
        except Exception as exc:
            console.print(f"  [red]✗ {callsign}: {exc}[/red]")
    console.print(f"[green]完成: {success_count}/{total_count} 架无人机已切换[/green]\n")
    display_live_status()


def adjust_all_zoom(direction: str):
    step = 5 if direction == "in" else -5
    action_name = "增加" if direction == "in" else "减少"
    console.print(f"\n[bold cyan]{action_name}所有变焦倍数 ({step:+d}x)[/bold cyan]")
    success_count, total_count = 0, 0
    for sn, state in live_states.items():
        if not state["video_id"] or state["lens_type"] != "zoom":
            continue
        total_count += 1
        if _adjust_one_zoom(sn, state, step, action_name):
            success_count += 1
    if total_count == 0:
        console.print("[yellow]没有无人机处于变焦模式[/yellow]\n")
    else:
        console.print(f"[green]完成: {success_count}/{total_count} 架无人机已调整[/green]\n")
    display_live_status()


def _adjust_one_zoom(sn: str, state: dict, step: int, action_name: str) -> bool:
    conn = connections[sn]
    callsign = conn["config"]["callsign"]
    current_zoom = state["zoom_factor"]
    new_zoom = max(1, min(112, current_zoom + step))
    if new_zoom == current_zoom:
        console.print(f"  [yellow]- {callsign}: 已达到{action_name}限制 ({current_zoom}x)[/yellow]")
        return False
    try:
        payload_index = conn["mqtt"].get_payload_index() or "39-0-7"
        set_camera_zoom(conn["mqtt"], payload_index, new_zoom, camera_type="zoom")
        state["zoom_factor"] = new_zoom
        console.print(f"  [green]✓ {callsign}: {current_zoom}x → {new_zoom}x[/green]")
        return True
    except Exception as exc:
        console.print(f"  [red]✗ {callsign}: {exc}[/red]")
        return False

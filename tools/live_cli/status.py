from __future__ import annotations

from rich.console import Console
from rich.table import Table

from .config import QUALITY_NAMES, RTMP_BASE_URL, connections, live_states

console = Console()


def display_live_status():
    table = Table(
        title="[bold cyan]直播状态监控[/bold cyan]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("呼号", style="cyan")
    table.add_column("序列号", style="yellow")
    table.add_column("直播状态", style="green")
    table.add_column("镜头/变焦", style="magenta")
    table.add_column("推流地址", style="blue")

    for sn, state in live_states.items():
        conn = connections[sn]
        callsign = conn["config"]["callsign"]
        status, lens_info = _state_labels(state)
        rtmp_url = f"{RTMP_BASE_URL}{conn['config']['rtmp_stream_key']}"
        table.add_row(callsign, sn, status, lens_info, rtmp_url)
    console.print(table)


def _state_labels(state: dict) -> tuple[str, str]:
    if not state["video_id"]:
        return "🔴 未启动", "-"
    quality_name = QUALITY_NAMES[state["quality"]]
    lens_name = "变焦" if state["lens_type"] == "zoom" else "广角"
    lens_info = (
        f"{lens_name} {state['zoom_factor']}x" if state["lens_type"] == "zoom" else lens_name
    )
    return f"🟢 运行中 ({quality_name})", lens_info

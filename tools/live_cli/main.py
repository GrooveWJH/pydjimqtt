from __future__ import annotations

import sys
import time

from rich.console import Console

from .controls import adjust_all_zoom, change_all_quality, read_key_nonblocking, toggle_all_lens
from .selection import select_uavs
from .session import cleanup_resources, connect_selected_uavs, start_all_live_streams
from .status import display_live_status

console = Console()


def main():
    console.print("\n" + "=" * 70)
    console.print("[bold cyan]DJI 无人机 RTMP 直播工具 - 多机版本[/bold cyan]")
    console.print("==" * 70 + "\n")
    selected_uavs = select_uavs()
    console.print("\n[bold cyan]========== 建立 DRC 连接 ==========[/bold cyan]\n")
    connect_selected_uavs(selected_uavs)
    try:
        console.print("[bold cyan]========== 启动直播推流 ==========[/bold cyan]\n")
        start_all_live_streams()
        console.print("\n[bold cyan]========== 直播状态 ==========[/bold cyan]\n")
        display_live_status()
        main_loop()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]收到中断信号[/yellow]")
    finally:
        cleanup_resources()


def main_loop():
    console.print("\n[bold yellow]所有直播运行中...[/bold yellow]")
    console.print("[dim]按键控制:[/dim]")
    console.print("[dim]  画质: 0=自适应 | 1=流畅 | 2=标清 | 3=高清 | 4=超清[/dim]")
    console.print("[dim]  变焦: z=放大 | x=缩小 (仅变焦模式, 1-112x)[/dim]")
    console.print("[dim]  镜头: o=切换 (变焦 ↔ 广角)[/dim]")
    console.print("[dim]  退出: Ctrl+C[/dim]\n")
    old_settings = _set_raw_terminal()
    try:
        while True:
            _handle_key(read_key_nonblocking())
            time.sleep(0.1)
    finally:
        _restore_terminal(old_settings)


def _handle_key(key: str | None) -> None:
    if not key:
        return
    if key in "01234":
        change_all_quality(int(key))
    elif key.lower() == "z":
        adjust_all_zoom("in")
    elif key.lower() == "x":
        adjust_all_zoom("out")
    elif key.lower() == "o":
        toggle_all_lens()


def _set_raw_terminal():
    if sys.platform == "win32":
        return None
    import termios
    import tty

    old_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    return old_settings


def _restore_terminal(old_settings) -> None:
    if old_settings:
        import termios

        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

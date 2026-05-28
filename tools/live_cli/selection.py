from __future__ import annotations

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from .config import RTMP_BASE_URL, UAV_CONFIGS

console = Console()


def display_uav_list():
    table = Table(
        title="[bold cyan]可用无人机列表[/bold cyan]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("编号", style="cyan", justify="center")
    table.add_column("名称", style="green")
    table.add_column("序列号", style="yellow")
    table.add_column("直播流", style="blue")
    for index, uav in enumerate(UAV_CONFIGS, 1):
        table.add_row(
            str(index),
            str(uav["name"]),
            str(uav["sn"]),
            f"{RTMP_BASE_URL}{uav['rtmp_stream_key']}",
        )
    console.print(table)


def select_uavs():
    display_uav_list()
    console.print("\n[bold cyan]选择启动模式:[/bold cyan]")
    console.print("  [1] 启动所有无人机")
    console.print("  [2] 选择特定无人机")
    choice = Prompt.ask("请选择", choices=["1", "2"], default="1")
    if choice == "1":
        return UAV_CONFIGS

    indices = Prompt.ask("\n输入要启动的无人机编号（多个用逗号分隔，如 1,3）", default="1")
    selected_indices = [int(value.strip()) - 1 for value in indices.split(",")]
    selected = [UAV_CONFIGS[index] for index in selected_indices if 0 <= index < len(UAV_CONFIGS)]
    console.print(f"\n[green]✓ 已选择 {len(selected)} 架无人机[/green]")
    return selected

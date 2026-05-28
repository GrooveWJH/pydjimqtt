"""MQTT sniffer CLI orchestration."""

import traceback

from rich.console import Console
from rich.live import Live

from pydjimqtt import HeartbeatHandle, MQTTClient, setup_drc_connection, stop_heartbeat

from .config import (
    ENABLE_DRC_MODE,
    GATEWAY_SN,
    HEARTBEAT_INTERVAL,
    HSI_FREQUENCY,
    MQTT_CONFIG,
    OSD_FREQUENCY,
    OUTPUT_BASE_DIR,
    SNIFF_TOPICS,
    USER_CALLSIGN,
    USER_ID,
)
from .core import TopicSniffer


def _connect(console: Console) -> tuple[MQTTClient, HeartbeatHandle | None]:
    if ENABLE_DRC_MODE:
        mqtt, _, heartbeat = setup_drc_connection(
            gateway_sn=GATEWAY_SN,
            mqtt_config=MQTT_CONFIG,
            user_id=USER_ID,
            user_callsign=USER_CALLSIGN,
            osd_frequency=OSD_FREQUENCY,
            hsi_frequency=HSI_FREQUENCY,
            heartbeat_interval=HEARTBEAT_INTERVAL,
            wait_for_user=True,
        )
        return mqtt, heartbeat

    console.print("[yellow]跳过 DRC 模式，仅连接 MQTT[/yellow]")
    mqtt = MQTTClient(GATEWAY_SN, MQTT_CONFIG)
    mqtt.connect()
    return mqtt, None


def _run_live_panel(console: Console, sniffer: TopicSniffer) -> None:
    with Live(sniffer.render_status(), refresh_per_second=2, console=console) as live:
        while True:
            import time

            time.sleep(0.5)
            live.update(sniffer.render_status())


def _print_saved_files(console: Console, output_dir) -> None:
    saved_files = list(output_dir.glob("*.json"))
    if not saved_files:
        return
    console.print("\n[bold cyan]已保存文件：[/bold cyan]")
    for file in sorted(saved_files):
        size = file.stat().st_size
        console.print(f"  [green]→[/green] {file.name} ({size:,} bytes)")


def main() -> int:
    console = Console()
    mqtt = None
    heartbeat = None
    sniffer = None

    try:
        console.rule("[bold cyan]建立连接[/bold cyan]")
        mqtt, heartbeat = _connect(console)

        console.rule("[bold cyan]启动 MQTT 嗅探器[/bold cyan]")
        console.print(f"[bold green]正在监听 {len(SNIFF_TOPICS)} 个 topic...[/bold green]")
        console.print("[bold yellow]按 Ctrl+C 停止嗅探、保存数据并退出。[/bold yellow]\n")
        sniffer = TopicSniffer(mqtt, SNIFF_TOPICS)
        _run_live_panel(console, sniffer)

    except KeyboardInterrupt:
        console.print("\n[yellow]检测到中断，正在停止...[/yellow]")
    except Exception as exc:
        console.print(f"\n[bold red]✗ 错误: {exc}[/bold red]")
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return 1
    finally:
        _cleanup(console, mqtt, heartbeat, sniffer)

    console.print("[green]✓ 嗅探完成[/green]")
    return 0


def _cleanup(
    console: Console,
    mqtt: MQTTClient | None,
    heartbeat: HeartbeatHandle | None,
    sniffer: TopicSniffer | None,
) -> None:
    if heartbeat:
        console.print("[cyan]停止心跳...[/cyan]")
        stop_heartbeat(heartbeat)

    if not mqtt:
        return

    if sniffer:
        console.print(f"[cyan]正在保存消息数据到 {OUTPUT_BASE_DIR}/...[/cyan]")
        output_dir = sniffer.save_to_directory(OUTPUT_BASE_DIR)
        console.print(f"[green]✓ 数据已保存到 {output_dir}/[/green]")
        _print_saved_files(console, output_dir)

    console.print("[cyan]断开 MQTT 连接...[/cyan]")
    mqtt.disconnect()

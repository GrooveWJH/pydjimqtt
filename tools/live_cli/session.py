from __future__ import annotations

import concurrent.futures

from rich.console import Console

from pydjimqtt import (
    setup_multiple_drc_connections,
    start_live,
    stop_heartbeat,
    stop_live,
    wait_for_camera_data,
)

from .config import (
    HSI_FREQUENCY,
    MQTT_CONFIG,
    OSD_FREQUENCY,
    RTMP_BASE_URL,
    STOP_LIVE_ON_EXIT,
    connections,
    live_states,
)

console = Console()


def connect_selected_uavs(selected_uavs):
    conn_list = setup_multiple_drc_connections(
        uav_configs=selected_uavs,
        mqtt_config=MQTT_CONFIG,
        osd_frequency=OSD_FREQUENCY,
        hsi_frequency=HSI_FREQUENCY,
        skip_drc_setup=True,
    )
    console.print(f"\n[green]✓ 已连接 {len(conn_list)} 架无人机[/green]\n")
    for (mqtt, caller, heartbeat), config in zip(conn_list, selected_uavs):
        sn = config["sn"]
        connections[sn] = {"mqtt": mqtt, "caller": caller, "heartbeat": heartbeat, "config": config}
        live_states[sn] = {"video_id": None, "quality": 0, "lens_type": "zoom", "zoom_factor": 2}


def start_all_live_streams():
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(start_live_for_uav, conn["mqtt"], conn["caller"], conn["config"]): sn
            for sn, conn in connections.items()
        }
        for future in concurrent.futures.as_completed(futures):
            sn = futures[future]
            try:
                live_states[sn]["video_id"] = future.result()
            except Exception as exc:
                console.print(f"[red]✗ {sn} 启动异常: {exc}[/red]")


def start_live_for_uav(mqtt, caller, config):
    callsign = config["callsign"]
    try:
        console.print(f"[{callsign}] 等待相机数据...")
        wait_for_camera_data(mqtt, max_wait=10)
        rtmp_url = f"{RTMP_BASE_URL}{config['rtmp_stream_key']}"
        console.print(f"[{callsign}] 推流地址: {rtmp_url}")
        video_id = start_live(caller, mqtt, rtmp_url, config["video_index"], video_quality=0)
        if video_id:
            console.print(
                f"[green]✓ [{callsign}] 直播已启动 (video_id: {video_id}, 质量: 自适应)[/green]"
            )
            return video_id
        console.print(f"[red]✗ [{callsign}] 直播启动失败[/red]")
        return None
    except Exception as exc:
        console.print(f"[red]✗ [{callsign}] 直播启动异常: {exc}[/red]")
        return None


def cleanup_resources():
    console.print("\n[bold cyan]========== 清理资源 ==========[/bold cyan]\n")
    if STOP_LIVE_ON_EXIT:
        _stop_live_streams()
    _disconnect_all()
    console.print("\n[bold green]✓ 清理完成[/bold green]\n")


def _stop_live_streams():
    console.print("[cyan]停止直播推流...[/cyan]")
    for sn, state in live_states.items():
        if not state["video_id"]:
            continue
        conn = connections[sn]
        callsign = conn["config"]["callsign"]
        try:
            stop_live(conn["caller"], state["video_id"])
            console.print(f"[green]✓ [{callsign}] 直播已停止[/green]")
        except Exception as exc:
            console.print(f"[red]✗ [{callsign}] 停止直播失败: {exc}[/red]")


def _disconnect_all():
    console.print("[cyan]断开连接...[/cyan]")
    for conn in connections.values():
        callsign = conn["config"]["callsign"]
        try:
            stop_heartbeat(conn["heartbeat"])
            conn["mqtt"].disconnect()
            console.print(f"[green]✓ [{callsign}] 连接已断开[/green]")
        except Exception as exc:
            console.print(f"[red]✗ [{callsign}] 断开失败: {exc}[/red]")

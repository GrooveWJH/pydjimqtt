from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ...core import MQTTClient, ServiceCaller
from ...mock.mock_drone import MockHeartbeatThread
from ..common import console
from ..heartbeat import HeartbeatHandle, start_heartbeat
from .control_auth import request_control_auth
from .live import enter_drc_mode


def setup_drc_connection(
    gateway_sn: str,
    mqtt_config: dict[str, Any],
    user_id: str = "pilot",
    user_callsign: str = "Callsign",
    osd_frequency: int = 30,
    hsi_frequency: int = 10,
    heartbeat_interval: float = 1.0,
    wait_for_user: bool = True,
    skip_drc_setup: bool = False,
) -> tuple[MQTTClient, ServiceCaller, HeartbeatHandle | None]:
    """Setup complete DRC connection in one call."""
    console.print(f"[bold cyan]设置 DRC 连接: {gateway_sn}[/bold cyan]")
    mqtt = MQTTClient(gateway_sn, mqtt_config)
    mqtt.connect()
    caller = ServiceCaller(mqtt)
    if skip_drc_setup:
        console.print("[bold yellow]仅连接 MQTT，跳过 DRC 模式设置[/bold yellow]")
        return mqtt, caller, None

    try:
        request_control_auth(caller, user_id=user_id, user_callsign=user_callsign)
        if wait_for_user:
            input("🔔 请在 DJI Pilot APP 上允许控制权，然后按 Enter 继续...")
        enter_drc_mode(
            caller,
            mqtt_broker=_mqtt_broker_config(gateway_sn, mqtt_config),
            osd_frequency=osd_frequency,
            hsi_frequency=hsi_frequency,
        )
        heartbeat = start_heartbeat(mqtt, interval=heartbeat_interval)
        console.print("[bold green]✓ DRC 连接设置完成[/bold green]")
        return mqtt, caller, heartbeat
    except Exception as exc:
        console.print(f"[red]✗ 设置失败: {exc}[/red]")
        mqtt.disconnect()
        raise


def setup_multiple_drc_connections(
    uav_configs: list[dict[str, Any]],
    mqtt_config: dict[str, Any],
    osd_frequency: int = 30,
    hsi_frequency: int = 10,
    heartbeat_interval: float = 1.0,
    skip_drc_setup: bool = False,
) -> list[tuple[MQTTClient, ServiceCaller, HeartbeatHandle]]:
    """Setup multiple DRC connections in parallel."""
    if skip_drc_setup:
        return _setup_mqtt_only_connections(uav_configs, mqtt_config)

    console.print(f"[bold cyan]并行设置 {len(uav_configs)} 架无人机的 DRC 连接[/bold cyan]\n")
    with ThreadPoolExecutor() as executor:
        phase1_results = list(executor.map(_connect_and_auth(mqtt_config), uav_configs))

    console.print(f"\n[green]✓ 已请求 {len(phase1_results)} 架无人机的控制权[/green]")
    input("\n🔔 请在 DJI Pilot APP 上允许所有无人机的控制权，然后按 Enter 继续...\n")

    def enter_and_start(result: tuple[str, MQTTClient, ServiceCaller]):
        sn, mqtt, caller = result
        console.print(f"[dim]设置 {sn} DRC 模式...[/dim]")
        enter_drc_mode(
            caller,
            mqtt_broker=_mqtt_broker_config(sn, mqtt_config),
            osd_frequency=osd_frequency,
            hsi_frequency=hsi_frequency,
        )
        return (mqtt, caller, start_heartbeat(mqtt, interval=heartbeat_interval))

    with ThreadPoolExecutor() as executor:
        connections = list(executor.map(enter_and_start, phase1_results))
    console.print(
        f"\n[bold green]✓ 所有无人机 DRC 连接设置完成 ({len(connections)} 架)[/bold green]\n"
    )
    return connections


def _setup_mqtt_only_connections(
    uav_configs: list[dict[str, Any]], mqtt_config: dict[str, Any]
) -> list[tuple[MQTTClient, ServiceCaller, HeartbeatHandle]]:
    console.print(f"[bold yellow]仅连接 MQTT ({len(uav_configs)} 架无人机)[/bold yellow]")
    console.print("[dim]跳过控制权请求和 DRC 模式设置[/dim]\n")
    connections = []
    for config in uav_configs:
        sn = config["sn"]
        console.print(f"[cyan]连接 {sn}...[/cyan]")
        mqtt = MQTTClient(sn, mqtt_config)
        mqtt.connect()
        caller = ServiceCaller(mqtt)
        thread = MockHeartbeatThread()
        heartbeat = HeartbeatHandle(thread=thread, stop_flag=thread.stop_flag)
        connections.append((mqtt, caller, heartbeat))
        console.print(f"[green]✓ {sn} MQTT 已连接[/green]")
    console.print(f"\n[bold green]✓ 所有 MQTT 连接已建立 ({len(connections)} 架)[/bold green]\n")
    return connections


def _connect_and_auth(mqtt_config: dict[str, Any]):
    def phase(config: dict[str, Any]) -> tuple[str, MQTTClient, ServiceCaller]:
        sn = config["sn"]
        console.print(f"[dim]连接 {sn}...[/dim]")
        mqtt = MQTTClient(sn, mqtt_config)
        mqtt.connect()
        caller = ServiceCaller(mqtt)
        request_control_auth(
            caller,
            user_id=config.get("user_id", "pilot"),
            user_callsign=config.get("callsign", "Callsign"),
        )
        return (sn, mqtt, caller)

    return phase


def _mqtt_broker_config(gateway_sn: str, mqtt_config: dict[str, Any]) -> dict[str, Any]:
    random_suffix = str(uuid.uuid4())[:3]
    return {
        "address": f"{mqtt_config['host']}:{mqtt_config['port']}",
        "client_id": f"drc-{gateway_sn}-{random_suffix}",
        "username": mqtt_config["username"],
        "password": mqtt_config["password"],
        "expire_time": int(time.time()) + 3600,
        "enable_tls": mqtt_config.get("enable_tls", False),
    }

#!/usr/bin/env python3
"""
DJI 无人机 RTMP 直播工具 - 多机版本

功能：
1. 支持多架无人机同时直播
2. 每架无人机独立的 RTMP 推流地址
3. 并行控制多个相机变焦
4. 统一启动/停止直播
"""

import sys
import os

# Add parent directory (pythonSDK/) to path to import pydjimqtt module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from pydjimqtt import (
    setup_multiple_drc_connections,
    stop_heartbeat,
    wait_for_camera_data,
    start_live,
    stop_live,
    set_live_quality,
    change_live_lens,
)
from pydjimqtt.services.drc_commands import set_camera_zoom
import time
import threading

console = Console()

# ========== 配置区域 ==========

# MQTT 配置
MQTT_CONFIG = {
    "host": "81.70.222.38",
    # 'host': '192.168.31.73',
    "port": 1883,
    "username": "dji",
    "password": "lab605605",
}

# 无人机配置列表（每架无人机有独立的直播地址）
UAV_CONFIGS = [
    {
        "name": "Drone001",
        "sn": "9N9CN2J0012CXY",
        "user_id": "pilot_1",
        "callsign": "Alpha",
        "rtmp_stream_key": "Drone001",  # RTMP 流名称（拼接到 base_url 后）
        "video_index": "normal-0",
        "video_quality": 4,  # 0=自适应, 1=流畅, 2=标清, 3=高清, 4=超清
        "zoom": {
            "enabled": True,  # 是否启用变焦控制
            "initial": 1,  # 初始变焦倍数
            "step": 1,  # 变焦步进
        },
    },
    {
        "name": "Drone002",
        "sn": "9N9CN8400164WH",
        "user_id": "pilot_2",
        "callsign": "Bravo",
        "rtmp_stream_key": "Drone002",
        "video_index": "normal-0",
        "video_quality": 4,
        "zoom": {
            "enabled": True,
            "initial": 1,
            "step": 1,
        },
    },
    {
        "name": "Drone003",
        "sn": "9N9CN180011TJN",
        "user_id": "pilot_3",
        "callsign": "Charlie",
        "rtmp_stream_key": "Drone003",
        "video_index": "normal-0",
        "video_quality": 4,
        "zoom": {
            "enabled": True,
            "initial": 1,
            "step": 1,
        },
    },
]

# RTMP 服务器配置
RTMP_BASE_URL = "rtmp://81.70.222.38:1935/live/"  # 基础 URL

# DRC 配置
OSD_FREQUENCY = 1  # Hz
HSI_FREQUENCY = 1  # Hz

# 控制程序结束时是否自动停止直播
STOP_LIVE_ON_EXIT = True

# ========== 全局状态 ==========

# 画质名称映射
QUALITY_NAMES = {0: "自适应", 1: "流畅", 2: "标清", 3: "高清", 4: "超清"}

# 分离固定连接和可变状态
connections = {}  # {sn: {'mqtt': ..., 'caller': ..., 'heartbeat': ..., 'config': ...}}
# {sn: {'video_id': None, 'quality': 0, 'lens_type': 'zoom', 'zoom_factor': 2}}
live_states = {}
stop_event = threading.Event()  # 用于停止所有控制线程


# ========== 工具函数 ==========


def display_uav_list():
    """显示无人机列表"""
    table = Table(
        title="[bold cyan]可用无人机列表[/bold cyan]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("编号", style="cyan", justify="center")
    table.add_column("名称", style="green")
    table.add_column("序列号", style="yellow")
    table.add_column("直播流", style="blue")

    for i, uav in enumerate(UAV_CONFIGS, 1):
        stream_url = f"{RTMP_BASE_URL}{uav['rtmp_stream_key']}"
        table.add_row(str(i), str(uav["name"]), str(uav["sn"]), stream_url)

    console.print(table)


def select_uavs():
    """让用户选择要启动的无人机"""
    display_uav_list()

    console.print("\n[bold cyan]选择启动模式:[/bold cyan]")
    console.print("  [1] 启动所有无人机")
    console.print("  [2] 选择特定无人机")

    choice = Prompt.ask("请选择", choices=["1", "2"], default="1")

    if choice == "1":
        return UAV_CONFIGS
    else:
        # 让用户选择特定无人机
        indices = Prompt.ask("\n输入要启动的无人机编号（多个用逗号分隔，如 1,3）", default="1")
        selected_indices = [int(i.strip()) - 1 for i in indices.split(",")]
        selected = [UAV_CONFIGS[i] for i in selected_indices if 0 <= i < len(UAV_CONFIGS)]

        console.print(f"\n[green]✓ 已选择 {len(selected)} 架无人机[/green]")
        return selected


def start_live_for_uav(mqtt, caller, config):
    """
    为单架无人机启动直播（永远用质量 0 - 自适应）

    Args:
        mqtt: MQTTClient
        caller: ServiceCaller
        config: 无人机配置

    Returns:
        video_id or None
    """
    callsign = config["callsign"]

    try:
        # 1. 等待相机数据
        console.print(f"[{callsign}] 等待相机数据...")
        wait_for_camera_data(mqtt, max_wait=10)

        # 2. 构建 RTMP URL
        rtmp_url = f"{RTMP_BASE_URL}{config['rtmp_stream_key']}"
        console.print(f"[{callsign}] 推流地址: {rtmp_url}")

        # 3. 启动直播（永远用质量 0 = 自适应）
        video_id_result = start_live(
            caller,
            mqtt,
            rtmp_url,
            config["video_index"],
            video_quality=0,  # 永远用自适应启动
        )

        if video_id_result:
            console.print(
                f"[green]✓ [{callsign}] 直播已启动 (video_id: {video_id_result}, 质量: 自适应)[/green]"
            )
            return video_id_result
        else:
            console.print(f"[red]✗ [{callsign}] 直播启动失败[/red]")
            return None

    except Exception as e:
        console.print(f"[red]✗ [{callsign}] 直播启动异常: {e}[/red]")
        return None


def zoom_control_thread(mqtt, config):
    """
    单架无人机的变焦控制线程

    监听键盘输入，控制变焦。
    由于多机场景下不好区分输入，这里暂时禁用键盘控制，
    改为在启动时设置初始变焦。

    如果需要实时控制，可以使用 Web UI 或其他控制方式。
    """
    # 多机场景下暂不支持键盘控制变焦
    # 可以扩展为 Web UI 控制
    pass


def read_key_nonblocking():
    """
    跨平台非阻塞键盘读取

    Returns:
        str: 读取到的按键字符，如果没有按键返回 None
    """
    if sys.platform == "win32":
        import msvcrt

        if msvcrt.kbhit():
            return msvcrt.getch().decode("utf-8")
    else:
        import select

        dr, dw, de = select.select([sys.stdin], [], [], 0)
        if dr:
            return sys.stdin.read(1)
    return None


def change_all_quality(new_quality):
    """
    修改所有无人机的直播质量

    Args:
        new_quality: 新的质量等级 (0-4)
    """
    quality_name = QUALITY_NAMES.get(new_quality, "未知")
    console.print(f"\n[bold cyan]切换所有直播到质量 {new_quality} ({quality_name})[/bold cyan]")

    success_count = 0
    total_count = 0

    for sn, state in live_states.items():
        if not state["video_id"]:
            continue  # 跳过未启动的

        total_count += 1
        conn = connections[sn]
        callsign = conn["config"]["callsign"]

        try:
            set_live_quality(conn["caller"], state["video_id"], new_quality)
            state["quality"] = new_quality  # 更新状态
            success_count += 1
            console.print(f"  [green]✓ {callsign}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {callsign}: {e}[/red]")

    console.print(f"[green]完成: {success_count}/{total_count} 架无人机已切换[/green]\n")

    # 刷新显示
    display_live_status()


def toggle_all_lens():
    """
    切换所有无人机的镜头类型（变焦 ↔ 广角）

    注意：仅在直播运行时可用
    """
    console.print("\n[bold cyan]切换所有直播镜头[/bold cyan]")

    success_count = 0
    total_count = 0

    for sn, state in live_states.items():
        if not state["video_id"]:
            continue  # 跳过未启动的

        total_count += 1
        conn = connections[sn]
        callsign = conn["config"]["callsign"]

        # 切换镜头类型
        current_lens = state["lens_type"]
        new_lens = "wide" if current_lens == "zoom" else "zoom"
        lens_name = "广角" if new_lens == "wide" else "变焦"

        try:
            change_live_lens(conn["caller"], state["video_id"], new_lens)
            state["lens_type"] = new_lens  # 更新状态
            success_count += 1
            console.print(f"  [green]✓ {callsign}: {lens_name}[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {callsign}: {e}[/red]")

    console.print(f"[green]完成: {success_count}/{total_count} 架无人机已切换[/green]\n")

    # 刷新显示
    display_live_status()


def adjust_all_zoom(direction: str):
    """
    调整所有无人机的变焦倍数

    Args:
        direction: 'in' 增加倍数，'out' 减少倍数

    注意：仅在变焦镜头模式下可用，范围 1-112x
    """
    step = 5 if direction == "in" else -5
    action_name = "增加" if direction == "in" else "减少"

    console.print(f"\n[bold cyan]{action_name}所有变焦倍数 ({step:+d}x)[/bold cyan]")

    success_count = 0
    total_count = 0

    for sn, state in live_states.items():
        if not state["video_id"]:
            continue  # 跳过未启动的

        # 仅在变焦模式下可用
        if state["lens_type"] != "zoom":
            continue

        total_count += 1
        conn = connections[sn]
        callsign = conn["config"]["callsign"]

        # 计算新的变焦倍数
        current_zoom = state["zoom_factor"]
        new_zoom = max(1, min(112, current_zoom + step))  # 限制在 1-112 范围

        # 如果没有变化，跳过
        if new_zoom == current_zoom:
            console.print(
                f"  [yellow]- {callsign}: 已达到{action_name}限制 ({current_zoom}x)[/yellow]"
            )
            continue

        try:
            # 获取 payload_index
            payload_index = conn["mqtt"].get_payload_index() or "39-0-7"

            set_camera_zoom(conn["mqtt"], payload_index, new_zoom, camera_type="zoom")
            state["zoom_factor"] = new_zoom  # 更新状态
            success_count += 1
            console.print(f"  [green]✓ {callsign}: {current_zoom}x → {new_zoom}x[/green]")
        except Exception as e:
            console.print(f"  [red]✗ {callsign}: {e}[/red]")

    if total_count == 0:
        console.print("[yellow]没有无人机处于变焦模式[/yellow]\n")
    else:
        console.print(f"[green]完成: {success_count}/{total_count} 架无人机已调整[/green]\n")

    # 刷新显示
    display_live_status()


def main_loop():
    """
    主循环 - 监听键盘输入控制画质、镜头和变焦

    按键功能：
    - 0-4: 切换画质
    - z: 变焦放大
    - x: 变焦缩小
    - o: 切换镜头（变焦 ↔ 广角）
    - Ctrl+C: 退出
    """
    console.print("\n[bold yellow]所有直播运行中...[/bold yellow]")
    console.print("[dim]按键控制:[/dim]")
    console.print("[dim]  画质: 0=自适应 | 1=流畅 | 2=标清 | 3=高清 | 4=超清[/dim]")
    console.print("[dim]  变焦: z=放大 | x=缩小 (仅变焦模式, 1-112x)[/dim]")
    console.print("[dim]  镜头: o=切换 (变焦 ↔ 广角)[/dim]")
    console.print("[dim]  退出: Ctrl+C[/dim]\n")

    # Unix/macOS: 设置终端为原始模式（非阻塞输入）
    old_settings = None
    if sys.platform != "win32":
        import termios
        import tty

        old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

    try:
        while True:
            key = read_key_nonblocking()
            if key:
                # 画质控制 (0-4)
                if key in "01234":
                    change_all_quality(int(key))
                # 变焦控制 (z/x)
                elif key.lower() == "z":
                    adjust_all_zoom("in")
                elif key.lower() == "x":
                    adjust_all_zoom("out")
                # 镜头切换 (o)
                elif key.lower() == "o":
                    toggle_all_lens()

            time.sleep(0.1)  # 100ms 轮询
    finally:
        # 恢复终端设置
        if old_settings:
            import termios

            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def display_live_status():
    """显示所有无人机的直播状态"""
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

        if state["video_id"]:
            quality_name = QUALITY_NAMES[state["quality"]]
            status = f"🟢 运行中 ({quality_name})"

            # 镜头和变焦信息
            lens_name = "变焦" if state["lens_type"] == "zoom" else "广角"
            if state["lens_type"] == "zoom":
                lens_info = f"{lens_name} {state['zoom_factor']}x"
            else:
                lens_info = lens_name
        else:
            status = "🔴 未启动"
            lens_info = "-"

        rtmp_url = f"{RTMP_BASE_URL}{conn['config']['rtmp_stream_key']}"
        table.add_row(callsign, sn, status, lens_info, rtmp_url)

    console.print(table)


# ========== 主程序 ==========


def main():
    console.print("\n" + "=" * 70)
    console.print("[bold cyan]DJI 无人机 RTMP 直播工具 - 多机版本[/bold cyan]")
    console.print("==" * 70 + "\n")

    # 步骤 1: 选择无人机
    selected_uavs = select_uavs()

    # 步骤 2: 建立 DRC 连接
    console.print("\n[bold cyan]========== 建立 DRC 连接 ==========[/bold cyan]\n")

    conn_list = setup_multiple_drc_connections(
        uav_configs=selected_uavs,
        mqtt_config=MQTT_CONFIG,
        osd_frequency=OSD_FREQUENCY,
        hsi_frequency=HSI_FREQUENCY,
        skip_drc_setup=True,
    )

    console.print(f"\n[green]✓ 已连接 {len(conn_list)} 架无人机[/green]\n")

    # 初始化全局状态：分离连接和状态
    for (mqtt, caller, heartbeat), config in zip(conn_list, selected_uavs):
        sn = config["sn"]
        connections[sn] = {
            "mqtt": mqtt,
            "caller": caller,
            "heartbeat": heartbeat,
            "config": config,
        }
        live_states[sn] = {
            "video_id": None,
            "quality": 0,  # 初始质量：自适应
            "lens_type": "zoom",  # 初始镜头：变焦
            "zoom_factor": 2,  # 初始变焦倍数：2x
        }

    try:
        # 步骤 3: 并行启动所有直播
        console.print("[bold cyan]========== 启动直播推流 ==========[/bold cyan]\n")

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(
                    start_live_for_uav, conn["mqtt"], conn["caller"], conn["config"]
                ): sn
                for sn, conn in connections.items()
            }

            for future in concurrent.futures.as_completed(futures):
                sn = futures[future]
                try:
                    video_id = future.result()
                    live_states[sn]["video_id"] = video_id
                except Exception as e:
                    console.print(f"[red]✗ {sn} 启动异常: {e}[/red]")

        # 步骤 4: 显示直播状态
        console.print("\n[bold cyan]========== 直播状态 ==========[/bold cyan]\n")
        display_live_status()

        # 步骤 5: 进入主循环（键盘控制画质）
        main_loop()

    except KeyboardInterrupt:
        console.print("\n\n[yellow]收到中断信号[/yellow]")

    finally:
        # 清理资源
        console.print("\n[bold cyan]========== 清理资源 ==========[/bold cyan]\n")

        # 停止所有直播
        if STOP_LIVE_ON_EXIT:
            console.print("[cyan]停止直播推流...[/cyan]")
            for sn, state in live_states.items():
                if state["video_id"]:
                    conn = connections[sn]
                    callsign = conn["config"]["callsign"]
                    try:
                        stop_live(conn["caller"], state["video_id"])
                        console.print(f"[green]✓ [{callsign}] 直播已停止[/green]")
                    except Exception as e:
                        console.print(f"[red]✗ [{callsign}] 停止直播失败: {e}[/red]")

        # 停止心跳和 MQTT 连接
        console.print("[cyan]断开连接...[/cyan]")
        for sn, conn in connections.items():
            callsign = conn["config"]["callsign"]
            try:
                stop_heartbeat(conn["heartbeat"])
                conn["mqtt"].disconnect()
                console.print(f"[green]✓ [{callsign}] 连接已断开[/green]")
            except Exception as e:
                console.print(f"[red]✗ [{callsign}] 断开失败: {e}[/red]")

        console.print("\n[bold green]✓ 清理完成[/bold green]\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        console.print(f"\n[bold red]程序异常: {e}[/bold red]")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")

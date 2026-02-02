#!/usr/bin/env python3
"""
DJI 无人机键盘控制（复用 keyboard.py 的输入逻辑）

配置参数请直接修改下方的 CONFIG 字典
"""

import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from pydjimqtt import (
    MQTTClient,
    ServiceCaller,
    enter_drc_mode,
    drone_emergency_stop,
    request_control_auth,
    send_stick_control,
    start_heartbeat,
    stop_heartbeat,
)

if TYPE_CHECKING:
    from pydjimqtt.utils.keyboard import JoystickApp  # noqa: F401

# ========== 配置参数 ==========
CONFIG = {
    "gateway_sn": "9N9CN2B00121JN",
    "mqtt_host": "192.168.10.90",
    "mqtt_port": 1883,
    "mqtt_username": "dji",
    "mqtt_password": "lab605605",
    "frequency": 30.0,
    "user_id": "keyboard_pilot",
    "user_callsign": "Keyboard Pilot",
    "in_drc_mode": False,
    "auto_confirm_auth": True,
    "osd_frequency": 100,
    "hsi_frequency": 10,
    "ui_scale": 1.0,
}


def _resolve_joystick_app():
    if __package__ is None:
        utils_dir = Path(__file__).resolve().parent
        project_root = utils_dir.parent
        src_root = project_root / "src"
        if str(utils_dir) not in sys.path:
            sys.path.insert(0, str(utils_dir))
        if str(src_root) not in sys.path:
            sys.path.insert(0, str(src_root))
        try:
            from keyboard import JoystickApp  # type: ignore
            return JoystickApp
        except ImportError as e:
            if (
                "X connection" in str(e)
                or "DISPLAY" in str(e)
                or "platform is not supported" in str(e)
            ):
                print("\n" + "=" * 80)
                print("❌ 错误: 键盘控制需要图形界面（X server）")
                print("=" * 80)
                print("\n🔧 解决方案：\n")
                print("1. 如果你在 SSH 连接中：")
                print("   - 使用 X11 转发: ssh -X user@host")
                print("   - 或者在本地运行此程序\n")
                print("2. 如果你在 WSL 中：")
                print("   - 安装 X server（如 VcXsrv、X410）")
                print("   - 设置 DISPLAY 环境变量: export DISPLAY=:0\n")
                print("3. 如果你在 Linux 服务器上：")
                print("   - 请在有桌面环境的机器上运行\n")
                print("4. 替代方案：")
                print("   - 使用 joystick UI: python main.py")
                print("   - 使用其他控制脚本（不需要键盘监听）\n")
                print("=" * 80 + "\n")
                sys.exit(1)
            raise
    from .keyboard import JoystickApp

    return JoystickApp


def main():
    JoystickApp = _resolve_joystick_app()
    from rich.console import Console
    from rich.panel import Panel
    import platform

    console = Console()
    console.print(
        Panel.fit(
            "[bold cyan]🚁 DJI 无人机键盘控制[/bold cyan]\n"
            f"[dim]SN: {CONFIG['gateway_sn']}[/dim]\n"
            f"[dim]MQTT: {CONFIG['mqtt_host']}:{CONFIG['mqtt_port']}[/dim]",
            border_style="cyan",
        )
    )

    # macOS 长按键盘提示
    if platform.system() == "Darwin":
        console.print("\n[bold yellow]⚠️  macOS 用户重要提示[/bold yellow]")
        console.print("[yellow]长按键盘可能会弹出字符选择器,影响无人机控制。[/yellow]")
        console.print("[yellow]解决方案（二选一）：[/yellow]")
        console.print(
            "[cyan]1. 临时禁用（推荐）: defaults write -g ApplePressAndHoldEnabled -bool false[/cyan]"
        )
        console.print("[cyan]2. 使用 Shift+P 暂停后切换窗口操作[/cyan]")
        console.print("[dim]提示：禁用后需要重启终端或重新登录生效[/dim]")
        console.print(
            "[dim]退出后可恢复: defaults write -g ApplePressAndHoldEnabled -bool true[/dim]\n"
        )

    # 1. 连接 MQTT
    console.print("[bold cyan]━━━ 步骤 1/4: 连接 MQTT ━━━[/bold cyan]")
    mqtt_client = MQTTClient(
        CONFIG["gateway_sn"],
        {
            "host": CONFIG["mqtt_host"],
            "port": CONFIG["mqtt_port"],
            "username": CONFIG["mqtt_username"],
            "password": CONFIG["mqtt_password"],
        },
    )
    try:
        mqtt_client.connect()
    except Exception as e:
        console.print(f"[red]✗ MQTT 连接失败: {e}[/red]")
        return 1

    caller = ServiceCaller(mqtt_client)
    in_drc_mode = CONFIG["in_drc_mode"]

    # 2-3. 请求控制权并进入 DRC 模式（如果需要）
    if not in_drc_mode:
        console.print("\n[bold cyan]━━━ 步骤 2/4: 请求控制权 ━━━[/bold cyan]")
        try:
            request_control_auth(
                caller, user_id=CONFIG["user_id"], user_callsign=CONFIG["user_callsign"]
            )
        except Exception as e:
            console.print(f"[red]✗ 控制权请求失败: {e}[/red]")
            mqtt_client.disconnect()
            return 1

        console.print(
            "\n[bold green]控制权请求已发送，请在遥控器上点击确认授权。[/bold green]"
        )
        if CONFIG["auto_confirm_auth"]:
            console.print("[bold cyan]自动等待 3 秒后继续...[/bold cyan]")
            time.sleep(3)
        else:
            console.print("[bold yellow]完成后按回车继续...[/bold yellow]")
            try:
                input()
            except KeyboardInterrupt:
                console.print("\n[yellow]检测到中断，退出。[/yellow]")
                mqtt_client.disconnect()
                return 1

        console.print("\n[bold cyan]━━━ 步骤 3/4: 进入 DRC 模式 ━━━[/bold cyan]")
        enter_drc_mode(
            caller,
            mqtt_broker={
                "address": f"{CONFIG['mqtt_host']}:{CONFIG['mqtt_port']}",
                "client_id": "drc-keyboard-control",
                "username": CONFIG["mqtt_username"],
                "password": CONFIG["mqtt_password"],
                "expire_time": int(time.time()) + 3600,
                "enable_tls": False,
            },
            osd_frequency=CONFIG["osd_frequency"],
            hsi_frequency=CONFIG["hsi_frequency"],
        )
    else:
        console.print("[bold green]✓ 已跳过控制权请求和进入 DRC 模式。[/bold green]")

    # 4. 启动心跳
    console.print("\n[bold cyan]━━━ 步骤 4/4: 启动心跳 ━━━[/bold cyan]")
    heartbeat_thread = start_heartbeat(mqtt_client, interval=0.2)

    console.print("\n[bold green]✓ 初始化完成！启动 TUI...[/bold green]")
    console.print("[green]✓ 自动焦点检测已启用（失去焦点时自动不响应）[/green]")
    console.print(
        "[bold cyan]💡 按 Shift+P 可暂停（暂停时可切换到其他窗口打字）[/bold cyan]\n"
    )

    try:
        # 定义 MQTT 发送回调（核心：唯一的新功能）
        def send_to_drone(stick_state):
            send_stick_control(
                mqtt_client,
                roll=stick_state["roll"],
                pitch=stick_state["pitch"],
                throttle=stick_state["throttle"],
                yaw=stick_state["yaw"],
            )

        def send_emergency_stop():
            drone_emergency_stop(mqtt_client)

        # 运行 App（复用 keyboard.py 的所有输入逻辑）
        app = JoystickApp(
            scale=CONFIG["ui_scale"],
            on_stick_update=send_to_drone,
            on_emergency_stop=send_emergency_stop,
            update_interval=1.0 / CONFIG["frequency"],
        )
        app.title = f"🚁 DJI 无人机键盘控制 - SN: {CONFIG['gateway_sn']}"
        app.run()

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ 收到中断信号[/yellow]")

    finally:
        # 清理资源
        console.print("\n[cyan]━━━ 清理资源 ━━━[/cyan]")
        console.print("[yellow]发送悬停指令...[/yellow]")
        for _ in range(5):
            send_stick_control(mqtt_client)
            time.sleep(0.1)
        stop_heartbeat(heartbeat_thread)
        mqtt_client.disconnect()
        console.print("[bold green]✓ 已安全退出[/bold green]")

    return 0


if __name__ == "__main__":
    exit(main())

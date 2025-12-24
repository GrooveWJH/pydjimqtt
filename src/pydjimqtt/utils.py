"""
DJI SDK 通用工具函数

包含：
- JSON 消息美化打印
- 键盘输入处理
- 相机数据等待
- Video ID 构建
"""
import time
import sys
import tty
import termios
import json
from typing import Optional, Tuple, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()


def print_json_message(title: str, data: Dict[str, Any], color: str = "cyan") -> None:
    """
    美化打印 JSON 消息

    Args:
        title: 标题
        data: JSON 数据（dict）
        color: 边框颜色

    Example:
        >>> print_json_message("Request", {"method": "live_start_push"}, "blue")
    """
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
    panel = Panel(
        syntax,
        title=f"[bold {color}]{title}[/bold {color}]",
        border_style=color,
        padding=(1, 2)
    )
    console.print("\n")
    console.print(panel)


def get_key() -> Optional[str]:
    """
    获取单个按键输入（非阻塞式）

    Returns:
        按键字符，或特殊键名（'UP', 'DOWN', 'LEFT', 'RIGHT', 'ESC'）

    Example:
        >>> key = get_key()
        >>> if key == 'UP':
        ...     print("向上箭头")
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        # 检测箭头键（转义序列）
        if ch == '\x1b':  # ESC
            ch2 = sys.stdin.read(1)
            if ch2 == '[':
                ch3 = sys.stdin.read(1)
                if ch3 == 'A':
                    return 'UP'
                elif ch3 == 'B':
                    return 'DOWN'
                elif ch3 == 'C':
                    return 'RIGHT'
                elif ch3 == 'D':
                    return 'LEFT'
            return 'ESC'
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def wait_for_camera_data(mqtt_client, max_wait: int = 10) -> Tuple[Optional[str], Optional[str]]:
    """
    等待相机数据到达

    Args:
        mqtt_client: MQTT 客户端（需要有 get_aircraft_sn() 和 get_payload_index() 方法）
        max_wait: 最大等待时间（秒）

    Returns:
        (aircraft_sn, payload_index) 或 (None, None) 如果超时

    Example:
        >>> aircraft_sn, payload_index = wait_for_camera_data(mqtt, max_wait=10)
        >>> if aircraft_sn and payload_index:
        ...     print(f"相机已连接: {aircraft_sn}/{payload_index}")
    """
    console.print(f"\n[yellow]⏳ 等待相机数据（最多 {max_wait} 秒）...[/yellow]")

    start_time = time.time()
    while time.time() - start_time < max_wait:
        aircraft_sn = mqtt_client.get_aircraft_sn()
        payload_index = mqtt_client.get_payload_index()

        if aircraft_sn and payload_index:
            console.print(f"[green]✓ 无人机 SN: {aircraft_sn}[/green]")
            console.print(f"[green]✓ 相机索引: {payload_index}[/green]")
            return aircraft_sn, payload_index

        time.sleep(0.5)

    console.print("[yellow]⚠ 超时，将使用默认值[/yellow]")
    return None, None


def build_video_id(mqtt_client, video_index: str = "normal-0") -> str:
    """
    构建 video_id

    Args:
        mqtt_client: MQTT 客户端（需要有 get_aircraft_sn(), get_payload_index(), gateway_sn 属性）
        video_index: 视频流索引（默认 "normal-0"）

    Returns:
        video_id 字符串，格式: {aircraft_sn}/{payload_index}/{video_index}

    Example:
        >>> video_id = build_video_id(mqtt, video_index="normal-0")
        >>> print(video_id)  # "1234567890ABC/88-0-0/normal-0"
    """
    aircraft_sn = mqtt_client.get_aircraft_sn() or mqtt_client.gateway_sn
    payload_index = mqtt_client.get_payload_index() or "88-0-0"
    return f"{aircraft_sn}/{payload_index}/{video_index}"

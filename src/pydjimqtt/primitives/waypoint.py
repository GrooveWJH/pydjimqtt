"""
航点导航原语
"""
import time
from typing import Dict, Any, Tuple, Optional
from rich.console import Console
from ..services import fly_to_point
from ..core import ServiceCaller, MQTTClient

console = Console()


def fly_to_waypoint(
    caller: ServiceCaller,
    lat: float,
    lon: float,
    height: float,
    max_speed: int = 12
) -> Dict[str, Any]:
    """
    飞向单个航点（封装 fly_to_point）

    Args:
        caller: 服务调用器
        lat: 纬度
        lon: 经度
        height: 高度（椭球高，米）
        max_speed: 最大速度（m/s）

    Returns:
        服务返回数据

    Example:
        >>> fly_to_waypoint(caller, lat=39.0427514, lon=117.7238255, height=100.0)
    """
    return fly_to_point(
        caller,
        latitude=lat,
        longitude=lon,
        height=height,
        max_speed=max_speed
    )


def monitor_flyto_progress(
    mqtt: MQTTClient,
    callsign: Optional[str] = None,
    show_progress: bool = True
) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    监控 Fly-to 进度（通用原语）

    Args:
        mqtt: MQTT客户端
        callsign: 无人机呼号（可选，用于显示）
        show_progress: 是否显示进度信息

    Returns:
        (status, progress) 元组
        - status: 'wayline_ok' | 'wayline_failed' | 'wayline_cancel' | 'wayline_progress' | None
        - progress: 完整的进度数据字典

    Example:
        >>> status, progress = monitor_flyto_progress(mqtt, callsign="Alpha")
        >>> if status == 'wayline_ok':
        >>>     print("到达航点！")
    """
    progress = mqtt.get_flyto_progress()
    status = progress.get('status')

    # 完成状态（成功、失败、取消）
    if status in ['wayline_ok', 'wayline_failed', 'wayline_cancel']:
        return status, progress

    # 进行中状态
    if show_progress and status == 'wayline_progress':
        remaining_distance = progress.get('remaining_distance')
        remaining_time = progress.get('remaining_time')

        if remaining_distance is not None and remaining_time is not None:
            timestamp = time.strftime('%H:%M:%S')
            if callsign:
                console.print(
                    f"[dim]{timestamp}[/dim] | "
                    f"[cyan]{callsign}[/cyan]: "
                    f"[yellow]剩余 {remaining_distance:.1f}m, {remaining_time:.1f}s[/yellow]"
                )
            else:
                console.print(
                    f"[dim]{timestamp}[/dim] | "
                    f"[yellow]剩余 {remaining_distance:.1f}m, {remaining_time:.1f}s[/yellow]"
                )

    return status, progress

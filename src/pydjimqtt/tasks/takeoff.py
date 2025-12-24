"""
起飞任务模板
"""
import time
from typing import Callable
from rich.console import Console

from ..services import send_stick_control
from ..primitives import wait_for_condition, send_stick_repeatedly
from .runner import MissionRunner

console = Console()


def create_takeoff_mission(
    target_height: float,
    height_tolerance: float = 0.1,
    throttle_offset: int = 300
) -> Callable[[MissionRunner], None]:
    """
    创建起飞任务函数（工厂模式）

    Args:
        target_height: 目标高度（米），必须 >= 5.0m
        height_tolerance: 高度容差（米），停止上升的精度
        throttle_offset: 油门偏移量（杆量），相对中值1024的偏移

    Returns:
        任务函数，可用于 run_parallel_missions

    Raises:
        ValueError: target_height < 5.0m

    Example:
        >>> takeoff_mission = create_takeoff_mission(
        >>>     target_height=10.0,
        >>>     height_tolerance=0.1,
        >>>     throttle_offset=300
        >>> )
        >>> runners = run_parallel_missions(connections, takeoff_mission, uav_configs)
    """
    # 参数验证
    if target_height < 5.0:
        raise ValueError(f"[red]✗ 安全限制：目标高度必须 >= 5.0m（当前值: {target_height}m）[/red]")

    if height_tolerance < 0 or height_tolerance > 1.0:
        raise ValueError(f"[red]✗ 高度容差必须在 0-1.0m 之间（当前值: {height_tolerance}m）[/red]")

    if throttle_offset < 0 or throttle_offset > 660:
        raise ValueError(f"[red]✗ 油门偏移必须在 0-660 之间（当前值: {throttle_offset}）[/red]")

    def takeoff_mission(runner: MissionRunner) -> None:
        """
        起飞任务逻辑：外八解锁 → 上升到目标高度 → 悬停

        Args:
            runner: MissionRunner 实例
        """
        mqtt = runner.mqtt
        callsign = runner.config['callsign']
        target = target_height - height_tolerance
        throttle_up = 1024 + throttle_offset

        # 阶段1: 等待GPS数据
        runner.status = "等待高度数据"
        wait_for_condition(lambda: mqtt.get_height() is not None, timeout=30)
        console.print(
            f"[green]✓ [{callsign}] GPS数据就绪，起飞点高度: {mqtt.get_height():.2f}m[/green]")

        # 阶段2: 解锁（外八：左摇杆左下 + 右摇杆右下）
        runner.status = "解锁中"
        console.print(f"[cyan][{callsign}] 外八解锁，持续 3秒...[/cyan]")
        send_stick_repeatedly(
            mqtt,
            roll=1684,      # 右摇杆右（横滚最右）
            pitch=364,      # 右摇杆下（俯仰最后）
            throttle=364,   # 左摇杆下（油门最低）
            yaw=364,        # 左摇杆左（偏航最左）
            duration=3.0,
            frequency=10
        )
        console.print(f"[green]✓ [{callsign}] 解锁完成[/green]")

        # 阶段3: 上升（带无法运动检测）
        runner.status = "上升中"
        console.print(
            f"[bold cyan][{callsign}] 开始上升，目标高度: {target_height}m[/bold cyan]")

        # 无法运动检测：记录初始状态
        start_time = time.time()
        last_check_time = start_time
        last_check_height = mqtt.get_relative_height() or 0.0
        stuck_threshold = 0.1  # 高度变化阈值（米）
        check_interval = 5.0   # 检查间隔（秒）

        while runner.running:
            h = mqtt.get_relative_height()
            if h is None:
                time.sleep(0.1)
                continue

            runner.data['height'] = h

            # 检查是否到达目标高度
            if h >= target:
                console.print(
                    f"[bold green]✓ [{callsign}] 到达目标高度: {h:.2f}m[/bold green]")
                break

            # 无法运动检测：每5秒检查一次
            current_time = time.time()
            if current_time - last_check_time >= check_interval:
                height_change = abs(h - last_check_height)

                if height_change < stuck_threshold:
                    # 5秒内高度变化小于0.1m，判定无法运动
                    console.print(
                        f"[bold red]✗ [{callsign}] 检测到无法运动！[/bold red]")
                    console.print(
                        f"[yellow]  · 时间间隔: {check_interval}s[/yellow]")
                    console.print(
                        f"[yellow]  · 高度变化: {height_change:.3f}m (阈值: {stuck_threshold}m)[/yellow]")
                    console.print(
                        f"[yellow]  · 当前高度: {h:.2f}m → 目标: {target_height}m[/yellow]")

                    # 停止发送杆量，归中遥杆
                    console.print(f"[yellow][{callsign}] 停止上升，归中遥杆...[/yellow]")
                    send_stick_repeatedly(mqtt, duration=1.0, frequency=10)

                    # 标记失败并退出
                    runner.status = "起飞失败：无法运动"
                    raise RuntimeError(
                        f"[{callsign}] 起飞失败：5秒内高度变化仅 {height_change:.3f}m，无法继续上升"
                    )

                # 更新检测基准
                last_check_time = current_time
                last_check_height = h

            # 继续上升
            send_stick_control(mqtt, throttle=throttle_up)
            time.sleep(0.1)

        # 阶段4: 悬停
        runner.status = "悬停"
        console.print(f"[yellow][{callsign}] 油门归中，保持悬停...[/yellow]")
        send_stick_repeatedly(mqtt, duration=5.0, frequency=10)

        runner.status = "起飞完成"
        final_height = runner.data.get('height', 0)
        console.print(
            f"[bold green]✓ [{callsign}] 起飞完成！最终高度: {final_height:.2f}m[/bold green]")

    return takeoff_mission

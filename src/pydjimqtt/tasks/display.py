"""
任务进度显示模块 - Rich 表格生成工具

提供可复用的 Rich 表格生成函数，用于实时监控多无人机任务执行状态。
这些函数设计为通用工具，可在任何需要显示任务进度的应用中使用。
"""
from typing import List, Dict, Any
from rich.table import Table


def create_takeoff_table(runners: List['MissionRunner']) -> Table:
    """
    创建起飞状态监控表格

    从 MissionRunner 列表读取状态和高度数据，生成实时监控表格。

    期望的 runner 数据结构:
        - runner.config['callsign']: 无人机呼号
        - runner.config['sn']: 网关序列号
        - runner.status: 任务状态字符串（如 "上升中", "任务完成"）
        - runner.data['height']: 当前高度（米）

    Args:
        runners: MissionRunner 对象列表

    Returns:
        Rich Table 对象，包含起飞进度信息

    Example:
        >>> from rich.live import Live
        >>> from rich.console import Console
        >>>
        >>> console = Console()
        >>> with Live(create_takeoff_table(runners), refresh_per_second=4, console=console) as live:
        >>>     while any(r.running for r in runners):
        >>>         live.update(create_takeoff_table(runners))
        >>>         time.sleep(0.25)
    """
    table = Table(title="[bold bright_cyan]起飞进度监控[/bold bright_cyan]", show_header=True)
    table.add_column("无人机", style="bright_yellow", width=10)
    table.add_column("序列号", style="bright_cyan", width=16)
    table.add_column("状态", style="bold", width=20)
    table.add_column("当前高度", style="bright_green", width=12)

    for runner in runners:
        callsign = runner.config.get('callsign', 'UAV')
        sn = runner.config.get('sn', 'N/A')
        status = runner.status
        height = runner.data.get('height', 0.0) if runner.data else 0.0

        # 状态颜色
        if "完成" in status or "任务完成" in status:
            status_color = "bright_green"
        elif "上升" in status:
            status_color = "bright_yellow"
        elif "错误" in status:
            status_color = "bright_red"
        else:
            status_color = "bright_cyan"

        table.add_row(
            callsign,
            sn,
            f"[{status_color}]{status}[/{status_color}]",
            f"{height:.2f}m" if height is not None else "N/A"
        )

    return table


def create_trajectory_table(runners: List['MissionRunner'], mission_state: Dict[str, Any]) -> Table:
    """
    创建轨迹飞行进度监控表格

    从 MissionRunner 列表和任务状态字典读取实时进度，生成监控表格。

    期望的 runner 数据结构:
        - runner.config['callsign']: 无人机呼号
        - runner.data['current_waypoint']: 当前航点索引（0-based）
        - runner.data['remaining_distance']: 剩余距离（米）
        - runner.data['remaining_time']: 预计剩余时间（秒）
        - runner.data['task_status']: 任务状态（如 "飞行中", "完成", "失败"）

    期望的 mission_state 数据结构:
        {
            'callsign': {
                'total_waypoints': 10,  # 总航点数
                'trajectory_file': 'Trajectory/uav1.json',
                'timestamp': 1699000000.0
            }
        }

    Args:
        runners: MissionRunner 对象列表
        mission_state: 任务元数据字典（包含各无人机的总航点数等信息）

    Returns:
        Rich Table 对象，包含轨迹飞行进度信息

    Example:
        >>> from rich.live import Live
        >>> from rich.console import Console
        >>>
        >>> console = Console()
        >>> mission_state = {
        >>>     'Alpha': {'total_waypoints': 10},
        >>>     'Bravo': {'total_waypoints': 8}
        >>> }
        >>>
        >>> with Live(create_trajectory_table(runners, mission_state), refresh_per_second=2, console=console) as live:
        >>>     while not all_done:
        >>>         live.update(create_trajectory_table(runners, mission_state))
        >>>         time.sleep(0.5)
    """
    table = Table(title="[bold bright_cyan]轨迹飞行实时进度[/bold bright_cyan]", show_header=True)
    table.add_column("无人机", style="bright_yellow", width=10)
    table.add_column("任务状态", style="bold", width=18)
    table.add_column("航点进度", style="bright_magenta", width=12)
    table.add_column("剩余距离", style="bright_green", width=12)
    table.add_column("预计时间", style="bright_cyan", width=12)

    for runner in runners:
        callsign = runner.config.get('callsign', 'UAV')

        # 从 runner.data 读取进度信息
        current_wp = runner.data.get('current_waypoint', 0)
        total_wp = mission_state.get(callsign, {}).get('total_waypoints', 0)
        remaining_dist = runner.data.get('remaining_distance')
        remaining_time = runner.data.get('remaining_time')
        task_status = runner.data.get('task_status', '准备中')

        # 状态颜色
        if '完成' in task_status:
            status_color = "bright_green"
        elif '飞行中' in task_status:
            status_color = "bright_yellow"
        elif '失败' in task_status or '错误' in task_status:
            status_color = "bright_red"
        else:
            status_color = "bright_cyan"

        # 航点进度
        if current_wp > 0 and total_wp > 0:
            wp_progress = f"{current_wp}/{total_wp}"
        elif total_wp > 0:
            wp_progress = f"0/{total_wp}"
        else:
            wp_progress = "N/A"

        # 剩余距离
        dist_str = f"{remaining_dist:.1f}m" if remaining_dist is not None else "N/A"

        # 预计时间
        time_str = f"{remaining_time:.1f}s" if remaining_time is not None else "N/A"

        table.add_row(
            callsign,
            f"[{status_color}]{task_status}[/{status_color}]",
            wp_progress,
            dist_str,
            time_str
        )

    return table

"""
任务执行框架 - 并行任务管理和状态监控
"""

import time
import threading
from typing import Callable, Dict, Any, List, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.live import Live

from ..core import MQTTClient, ServiceCaller
from ..services import stop_heartbeat
from ..primitives import send_stick_repeatedly

console = Console()


class MissionRunner:
    """任务执行器 - 管理单个无人机的任务执行"""

    def __init__(
        self,
        mqtt: MQTTClient,
        caller: ServiceCaller,
        heartbeat: threading.Thread,
        config: Dict[str, Any],
    ):
        """
        初始化任务执行器

        Args:
            mqtt: MQTT客户端
            caller: 服务调用器
            heartbeat: 心跳线程
            config: 配置字典（必须包含 'callsign' 和 'sn'）
        """
        self.mqtt = mqtt
        self.caller = caller
        self.heartbeat = heartbeat
        self.config = config
        self.status = "初始化"
        self.data: Dict[str, Any] = {}  # 任务数据（如当前高度）
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def run(self, mission_func: Callable[["MissionRunner"], None]) -> None:
        """
        在后台线程运行任务

        Args:
            mission_func: 任务函数，接收 MissionRunner 作为参数
        """
        self.running = True
        self.thread = threading.Thread(
            target=self._run_with_error_handling, args=(mission_func,), daemon=True
        )
        self.thread.start()

    def _run_with_error_handling(
        self, mission_func: Callable[["MissionRunner"], None]
    ) -> None:
        """带错误处理的任务执行"""
        try:
            mission_func(self)
        except Exception as e:
            self.status = f"错误: {e}"
            console.print(f"[red]✗ [{self.config['callsign']}] 任务失败: {e}[/red]")
        finally:
            self.running = False

    def stop(self) -> None:
        """停止任务"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)


def create_status_table(runners: List[MissionRunner]) -> Table:
    """
    创建任务状态监控表格

    Args:
        runners: 任务执行器列表

    Returns:
        Rich Table 对象
    """
    table = Table(title="[bold cyan]任务状态监控[/bold cyan]", show_header=True)
    table.add_column("无人机", style="bold yellow", width=10)
    table.add_column("序列号", style="cyan", width=16)
    table.add_column("状态", style="bold", width=15)
    table.add_column("数据", style="green", width=20)

    for runner in runners:
        # 状态颜色
        status_color = "cyan"
        if "完成" in runner.status or "任务完成" in runner.status:
            status_color = "green"
        elif runner.status.startswith("错误"):
            status_color = "red"
        elif "上升" in runner.status or "降落" in runner.status:
            status_color = "yellow"

        # 数据显示
        data_str = ""
        if "height" in runner.data and runner.data["height"] is not None:
            data_str = f"高度: {runner.data['height']:.2f}m"
        elif runner.data:
            data_str = ", ".join(f"{k}: {v}" for k, v in list(runner.data.items())[:2])

        table.add_row(
            runner.config["callsign"],
            runner.config["sn"],
            f"[{status_color}]{runner.status}[/{status_color}]",
            data_str or "[dim]N/A[/dim]",
        )

    return table


def run_parallel_missions(
    connections: List[Tuple[MQTTClient, ServiceCaller, threading.Thread]],
    mission_func: Callable[[MissionRunner], None]
    | List[Callable[[MissionRunner], None]],
    uav_configs: List[Dict[str, Any]],
    countdown: int = 3,
    show_monitor: bool = True,
) -> List[MissionRunner]:
    """
    并行运行多个无人机任务并实时监控

    Args:
        connections: 连接列表（来自 setup_multiple_drc_connections）
        mission_func: 任务函数或任务函数列表
                     - 如果是单个函数，所有无人机执行相同任务
                     - 如果是列表，每个无人机执行对应的任务
        uav_configs: 无人机配置列表
        countdown: 启动倒计时（秒）
        show_monitor: 是否显示实时监控表格（默认 True）

    Returns:
        任务执行器列表

    Example:
        >>> # 方式1: 所有无人机执行相同任务
        >>> def my_mission(runner):
        >>>     runner.status = "执行中"
        >>>     # ... 任务逻辑 ...
        >>>     runner.status = "完成"
        >>>
        >>> runners = run_parallel_missions(connections, my_mission, uav_configs)
        >>>
        >>> # 方式2: 每个无人机执行不同任务
        >>> missions = [create_takeoff_mission(h) for h in [90, 100, 110]]
        >>> runners = run_parallel_missions(connections, missions, uav_configs)
    """
    # 创建任务执行器
    runners: List[MissionRunner] = []
    for i, (mqtt, caller, heartbeat) in enumerate(connections):
        runner = MissionRunner(mqtt, caller, heartbeat, uav_configs[i])
        runners.append(runner)
        console.print(f"[green]✓ 无人机 {runner.config['callsign']} 初始化完成[/green]")

    # 倒计时
    if countdown > 0:
        console.print(f"\n[yellow]⚠️  任务将在{countdown}秒后开始...[/yellow]\n")
        for i in range(countdown, 0, -1):
            console.print(f"[bold yellow]{i}...[/bold yellow]")
            time.sleep(1)
        console.print("[bold green]▶ 任务开始！[/bold green]\n")

    # 启动所有任务
    if isinstance(mission_func, list):
        # 任务函数列表：每个无人机执行对应任务
        for runner, func in zip(runners, mission_func):
            runner.run(func)
    else:
        # 单一任务函数：所有无人机执行相同任务
        for runner in runners:
            runner.run(mission_func)

    # 实时监控（可选）
    if show_monitor:
        try:
            with Live(
                create_status_table(runners), refresh_per_second=4, console=console
            ) as live:
                while True:
                    if all(not r.running for r in runners):
                        break
                    live.update(create_status_table(runners))
                    time.sleep(0.25)
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ 收到中断信号，停止所有任务...[/yellow]")
            for runner in runners:
                runner.stop()
    else:
        # 不显示监控，仅等待任务完成
        try:
            while True:
                if all(not r.running for r in runners):
                    break
                time.sleep(0.5)
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ 收到中断信号，停止所有任务...[/yellow]")
            for runner in runners:
                runner.stop()

    return runners


def cleanup_missions(runners: List[MissionRunner], hover_duration: float = 1.0) -> None:
    """
    清理任务资源

    Args:
        runners: 任务执行器列表
        hover_duration: 悬停指令持续时间（秒）
    """
    console.print("\n[cyan]━━━ 清理资源 ━━━[/cyan]")

    # 发送悬停指令
    console.print("[yellow]发送悬停指令...[/yellow]")
    for runner in runners:
        send_stick_repeatedly(runner.mqtt, duration=hover_duration, frequency=10)

    # 停止心跳和断开连接
    for runner in runners:
        stop_heartbeat(runner.heartbeat)
        runner.mqtt.disconnect()

    console.print("[bold green]✓ 任务结束，所有资源已清理[/bold green]")

    # 显示最终统计
    console.print("\n[bold cyan]━━━ 任务统计 ━━━[/bold cyan]")
    for runner in runners:
        if "完成" in runner.status or "任务完成" in runner.status:
            data_info = ""
            if runner.data:
                data_info = ", " + ", ".join(
                    f"{k}: {v}" for k, v in list(runner.data.items())[:2]
                )
            console.print(
                f"[green]✓ {runner.config['callsign']}: {runner.status}{data_info}[/green]"
            )
        else:
            console.print(
                f"[yellow]⚠ {runner.config['callsign']}: {runner.status}[/yellow]"
            )

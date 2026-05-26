"""
轨迹飞行任务模块

提供多航点顺序飞行任务的高级封装，支持：
- 从 JSON 文件加载航点
- 依次飞向多个航点
- 实时监控飞行进度
- 航点间悬停稳定
"""

import time
import json
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any
from rich.console import Console

from ..services import fly_to_point, reset_gimbal, set_camera_zoom, change_live_lens
from ..utils import build_video_id
from .runner import MissionRunner

console = Console()

# 任务状态文件路径（进程间共享）
MISSION_STATE_FILE = Path("/tmp/pydjimqtt_mission_state.json")


def _update_mission_state_file(runner: MissionRunner, wp_index: int, task_status: str):
    """
    更新任务状态文件（原子写入，进程安全）

    Args:
        runner: MissionRunner 对象
        wp_index: 当前航点索引（1-based）
        task_status: 任务状态描述（如"飞行中"、"完成"等）

    Note:
        - 使用原子写入（temp file + rename）防止部分读取
        - 静默失败（写入失败不影响任务执行）
        - Dashboard 通过读取此文件显示任务进度
    """
    try:
        callsign = runner.config.get("callsign", "UAV")

        # 读取现有文件（保留其他无人机数据）
        mission_state = {}
        if MISSION_STATE_FILE.exists():
            with open(MISSION_STATE_FILE, "r") as f:
                mission_state = json.load(f)

        # 更新当前无人机数据
        mission_state[callsign] = {
            "current_waypoint": wp_index,
            "total_waypoints": runner.data.get("total_waypoints", 0),
            "task_status": task_status,
            "timestamp": time.time(),
            "trajectory_file": runner.config.get("trajectory_file", ""),
        }

        # 原子写入（先写临时文件，再重命名）
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, dir="/tmp", prefix="pydjimqtt_mission_"
        ) as tmp_file:
            json.dump(mission_state, tmp_file, indent=2)
            tmp_path = tmp_file.name

        # 原子替换
        shutil.move(tmp_path, MISSION_STATE_FILE)

    except Exception:
        # 静默失败：文件写入失败不影响任务执行
        pass


def load_trajectory(filepath: str) -> List[Dict[str, Any]]:
    """
    从 JSON 文件加载航点数据

    Args:
        filepath: 航点文件路径

    Returns:
        航点列表，每个航点包含:
        - id: 航点编号
        - lat: 纬度
        - lon: 经度

    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 格式错误
        ValueError: 数据格式错误

    Example:fly_trajectory_sequence()
        >>> waypoints = load_trajectory('Trajectory/uav1.json')
        >>> print(f"加载了 {len(waypoints)} 个航点")
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"航点文件不存在: {filepath}")

    with open(path, "r", encoding="utf-8") as f:
        waypoints = json.load(f)

    if not isinstance(waypoints, list) or len(waypoints) == 0:
        raise ValueError(f"航点数据格式错误或为空: {filepath}")

    # 验证航点数据格式
    for i, wp in enumerate(waypoints):
        if not isinstance(wp, dict):
            raise ValueError(f"航点 {i + 1} 数据格式错误: {wp}")
        if "lat" not in wp or "lon" not in wp:
            raise ValueError(f"航点 {i + 1} 缺少 lat 或 lon 字段: {wp}")

    return waypoints


def fly_trajectory_sequence(
    runners: List[MissionRunner],
    waypoints: List[Dict[str, Any]],
    height: float,
    max_speed: int = 12,
    hover_between_waypoints: float = 5.0,
    show_progress: bool = True,
    debug: bool = False,
) -> bool:
    """
    依次飞向多个航点（所有无人机并行执行相同轨迹）

    Args:
        runners: MissionRunner 列表
        waypoints: 航点列表，每个航点包含:
            - lat, lon: 必需
        height: 飞行高度（椭球高，米）
        max_speed: 最大速度（m/s，0-15）
        hover_between_waypoints: 航点间悬停时间（秒）
        show_progress: 是否显示进度信息
        debug: 是否打印调试信息（包括完整的 event 数据）

    Returns:
        是否全部成功

    Example:
        >>> waypoints = [
        >>>     {'id': 1, 'lat': 39.0427514, 'lon': 117.7238255},
        >>>     {'id': 2, 'lat': 39.0428000, 'lon': 117.7239000},
        >>> ]
        >>> success = fly_trajectory_sequence(runners, waypoints, height=100.0, debug=True)
    """
    total_waypoints = len(waypoints)
    all_success = True

    def _should_abort() -> bool:
        """外部停止信号（如返航）时立即终止后续航点"""
        return any(not r.running for r in runners)

    for wp_index, waypoint in enumerate(waypoints, 1):
        if _should_abort():
            for r in runners:
                _update_mission_state_file(r, wp_index - 1, "已取消")
            return False
        wp_id = waypoint.get("id", wp_index)
        lat = waypoint["lat"]
        lon = waypoint["lon"]

        # 更新所有 runner 的当前航点索引（供外部监控和 dashboard 显示）
        for runner in runners:
            runner.data["current_waypoint"] = wp_index
            # ✅ 立即写入文件（Dashboard 通过文件读取任务进度）
            _update_mission_state_file(runner, wp_index, "飞行中")

        if show_progress:
            console.print(
                f"\n[bold bright_cyan]━━━ 航点 {wp_index}/{total_waypoints} (ID: {wp_id}) ━━━[/bold bright_cyan]"
            )
            console.print(
                f"[bright_yellow]目标: lat={lat:.7f}, lon={lon:.7f}, h={height:.1f}m[/bright_yellow]"
            )

        # 发送 Fly-to 指令到所有无人机，并记录 fly_to_id
        fly_to_ids = {}  # {callsign: fly_to_id}
        for runner in runners:
            if _should_abort():
                for r in runners:
                    _update_mission_state_file(r, wp_index - 1, "已取消")
                return False

            caller = runner.caller
            callsign = runner.config.get("callsign", "UAV")
            if show_progress:
                console.print(f"[bright_cyan][{callsign}] 飞向航点 {wp_index}...[/bright_cyan]")

            try:
                fly_to_id = fly_to_point(
                    caller,
                    latitude=lat,
                    longitude=lon,
                    height=height,
                    max_speed=max_speed,
                )
                fly_to_ids[callsign] = fly_to_id
            except Exception as e:
                # service call 失败，立即终止整个轨迹任务
                console.print(
                    f"\n[bold bright_red]✗ [{callsign}] Fly-to service 调用失败，终止轨迹任务[/bold bright_red]"
                )
                console.print(f"[yellow]   航点: {wp_index}/{total_waypoints}[/yellow]")
                console.print(f"[yellow]   异常: {e}[/yellow]")

                # 更新失败状态到文件
                for r in runners:
                    _update_mission_state_file(r, wp_index, f"失败(航点{wp_index})")

                return False  # 立即返回失败

        # 监控飞行进度（实时打印距离、时间等信息）
        if show_progress:
            console.print("[dim]监控飞行进度（实时显示）...[/dim]\n")

        for runner in runners:
            mqtt = runner.mqtt
            callsign = runner.config.get("callsign", "UAV")

            # 跳过 service call 失败的无人机（用缺失 key 判断，不用 None）
            if callsign not in fly_to_ids:
                if show_progress:
                    console.print(f"[dim][{callsign}] 跳过监控（service call 失败）[/dim]")
                continue

            fly_to_id = fly_to_ids[callsign]

            # 实时监控飞行进度（自己实现循环，打印实时信息）
            try:
                if debug:
                    console.print(
                        f"[dim]🐛 [{callsign}] 等待 fly_to_id={fly_to_id[:8]}... 的事件[/dim]"
                    )

                start_time = time.time()
                terminal_statuses = {"wayline_ok", "wayline_failed", "wayline_cancel"}
                last_print_time = 0
                print_interval = 1.0  # 每秒打印一次进度

                while True:
                    if not runner.running:
                        all_success = False
                        _update_mission_state_file(runner, wp_index, "已取消")
                        break

                    elapsed = time.time() - start_time
                    if elapsed > 120.0:  # 2分钟超时
                        raise TimeoutError(
                            f"[{callsign}] 等待 fly_to_id={fly_to_id[:8]}... 的事件超时（120秒）"
                        )

                    # 读取最新飞行进度数据
                    progress = mqtt.get_flyto_progress()
                    event_fly_to_id = progress.get("fly_to_id")
                    status = progress.get("status")

                    # ✅ 关键检查：fly_to_id 必须匹配（防止读取旧航点数据）
                    if event_fly_to_id == fly_to_id:
                        # 收到当前航点的事件

                        # 实时打印飞行信息（每秒一次）
                        current_time = time.time()
                        if status == "wayline_progress" and show_progress:
                            if current_time - last_print_time >= print_interval:
                                remaining_distance = progress.get("remaining_distance")
                                remaining_time = progress.get("remaining_time")
                                way_point_index = progress.get("way_point_index")

                                # 构建进度信息字符串
                                info_parts = []
                                if remaining_distance is not None:
                                    info_parts.append(f"剩余距离: {remaining_distance:.1f}m")
                                if remaining_time is not None:
                                    info_parts.append(f"剩余时间: {remaining_time:.1f}s")
                                if way_point_index is not None:
                                    info_parts.append(f"航点索引: {way_point_index}")

                                info_str = " | ".join(info_parts) if info_parts else "飞行中..."

                                console.print(
                                    f"[bright_cyan]→ [{callsign}] 飞向航点 {wp_index}: {info_str}[/bright_cyan]"
                                )
                                last_print_time = current_time

                        # 调试：打印完整事件数据
                        if debug and status in terminal_statuses:
                            console.print(f"[dim]🐛 [{callsign}] 收到终止事件: {progress}[/dim]")

                        # 检查是否到达终止状态
                        if status in terminal_statuses:
                            result_code = progress.get("result")

                            if status == "wayline_ok":
                                if show_progress:
                                    console.print(
                                        f"[bold bright_green]✓ [{callsign}] 已到达航点 {wp_index}！[/bold bright_green]"
                                    )
                            elif status == "wayline_failed":
                                if show_progress:
                                    console.print(
                                        f"[bold bright_red]✗ [{callsign}] 飞向航点 {wp_index} 失败[/bold bright_red]"
                                    )
                                    console.print(f"[dim]   result_code: {result_code}[/dim]")
                                all_success = False
                            elif status == "wayline_cancel":
                                if show_progress:
                                    console.print(
                                        f"[bold bright_yellow]⚠ [{callsign}] 飞向航点 {wp_index} 取消[/bold bright_yellow]"
                                    )
                                    console.print(f"[dim]   result_code: {result_code}[/dim]")
                                all_success = False

                            # 到达终止状态，退出循环
                            break

                    # 短暂休眠（避免过度占用 CPU）
                    time.sleep(0.1)

            except TimeoutError as e:
                console.print(
                    f"[bold bright_red]✗ [{callsign}] 航点 {wp_index} 超时[/bold bright_red]"
                )
                console.print(f"[dim]   {e}[/dim]")
                all_success = False
            except Exception as e:
                console.print(
                    f"[bold bright_red]✗ [{callsign}] 航点 {wp_index} 异常[/bold bright_red]"
                )
                console.print(f"[dim]   {e}[/dim]")
                all_success = False

        if show_progress:
            console.print(
                f"[bold bright_green]✓ 航点 {wp_index}/{total_waypoints} 飞行完成[/bold bright_green]"
            )

        # 航点间等待（除了最后一个航点）
        if wp_index < total_waypoints and hover_between_waypoints > 0:
            if _should_abort():
                for r in runners:
                    _update_mission_state_file(r, wp_index, "已取消")
                return False

            if show_progress:
                console.print(f"[bright_cyan]━━━ 航点 {wp_index} 悬停操作 ━━━[/bright_cyan]")
                console.print(
                    f"[bright_yellow]悬停 {hover_between_waypoints:.1f} 秒，切换zoom镜头 + 云台朝下 + 变焦3倍[/bright_yellow]"
                )

            # 所有无人机：切换zoom镜头 + 云台朝下 + 变焦3倍
            for runner in runners:
                mqtt = runner.mqtt
                caller = runner.caller
                callsign = runner.config.get("callsign", "UAV")

                # 跳过之前失败的无人机
                if callsign not in fly_to_ids:
                    continue

                try:
                    payload_index = mqtt.get_payload_index() or "88-0-0"

                    # 1. 切换镜头到 zoom（使用 change_live_lens）
                    try:
                        video_id = build_video_id(mqtt, video_index="zoom-0")
                        if show_progress:
                            console.print(
                                f"[bright_cyan][{callsign}] 切换到zoom镜头...[/bright_cyan]"
                            )
                        change_live_lens(caller, video_id=video_id, video_type="zoom")
                    except Exception as e:
                        if show_progress:
                            console.print(
                                f"[bright_yellow]⚠ [{callsign}] 切换镜头失败: {e}[/bright_yellow]"
                            )

                    # 2. 云台朝下（reset_mode=1: yaw回中、pitch向下）
                    if show_progress:
                        console.print(f"[bright_cyan][{callsign}] 云台朝下...[/bright_cyan]")
                    reset_gimbal(mqtt, payload_index=payload_index, reset_mode=1)

                    # 3. 变焦3倍
                    if show_progress:
                        console.print(f"[bright_cyan][{callsign}] 变焦3倍...[/bright_cyan]")
                    set_camera_zoom(
                        mqtt,
                        payload_index=payload_index,
                        zoom_factor=3.0,
                        camera_type="zoom",
                    )

                except Exception as e:
                    if show_progress:
                        console.print(
                            f"[bright_yellow]⚠ [{callsign}] 云台/变焦控制失败: {e}[/bright_yellow]"
                        )

            # 悬停等待（fly_to_point 后飞机会自动悬停）
            time.sleep(hover_between_waypoints)

    # ✅ 任务完成，更新最终状态
    for runner in runners:
        final_status = f"完成 ({total_waypoints}航点)" if all_success else "任务失败"
        _update_mission_state_file(runner, total_waypoints, final_status)

    return all_success


def create_trajectory_mission(
    waypoints: List[Dict[str, Any]],
    height: float,
    max_speed: int = 12,
    hover_between_waypoints: float = 5.0,
    show_progress: bool = True,
    debug: bool = False,
):
    """
    创建轨迹飞行任务函数（用于 run_parallel_missions）

    这是一个高阶函数，返回一个任务函数，可以直接传给 run_parallel_missions。

    Args:
        waypoints: 航点列表
        height: 飞行高度（米）
        max_speed: 最大速度（m/s）
        hover_between_waypoints: 航点间悬停时间（秒）
        show_progress: 是否显示进度信息
        debug: 是否打印调试信息

    Returns:
        任务函数，签名: (runner: MissionRunner) -> None

    Example:
        >>> waypoints = load_trajectory('Trajectory/uav1.json')
        >>> mission = create_trajectory_mission(waypoints, height=100.0, debug=True)
        >>> runners = run_parallel_missions(connections, mission, uav_configs)
    """

    def trajectory_mission(runner: MissionRunner):
        """执行轨迹飞行任务"""
        # 单个无人机的轨迹飞行
        success = fly_trajectory_sequence(
            runners=[runner],
            waypoints=waypoints,
            height=height,
            max_speed=max_speed,
            hover_between_waypoints=hover_between_waypoints,
            show_progress=show_progress,
            debug=debug,
        )

        if not success:
            raise RuntimeError("轨迹飞行任务执行失败")

    return trajectory_mission

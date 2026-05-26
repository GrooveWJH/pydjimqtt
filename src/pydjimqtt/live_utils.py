"""
DJI SDK 直播相关高级工具

包含：
- 带详细日志的直播推流控制
- 键盘变焦控制循环
"""

import time
import threading
import uuid
from typing import Optional
from rich.console import Console
from .utils import print_json_message, get_key
from .services.drc_commands import set_camera_zoom

console = Console()


def start_live(
    caller,
    mqtt_client,
    rtmp_url: str,
    video_index: str = "normal-0",
    video_quality: int = 0,
) -> Optional[str]:
    """
    开始直播推流（带详细 MQTT 消息打印）

    Args:
        caller: 服务调用器
        mqtt_client: MQTT 客户端
        rtmp_url: RTMP 推流地址
        video_index: 视频流索引（默认 "normal-0"）
        video_quality: 视频质量 (0=自适应, 1=流畅, 2=标清, 3=高清, 4=超清)

    Returns:
        video_id: 用于停止直播的 video_id，失败返回 None

    Example:
        >>> video_id = start_live(caller, mqtt, "rtmp://server/live/stream")
        >>> if video_id:
        ...     print(f"直播已启动: {video_id}")
    """
    console.print("\n[bold cyan]========== 开始直播推流 ==========[/bold cyan]")

    # 构建 video_id
    from .utils import build_video_id

    video_id = build_video_id(mqtt_client, video_index)
    console.print(f"[cyan]Video ID:[/cyan] {video_id}")
    console.print(f"[cyan]RTMP URL:[/cyan] {rtmp_url}")
    console.print(
        f"[cyan]视频质量:[/cyan] {['自适应', '流畅', '标清', '高清', '超清'][video_quality]}"
    )

    # 构造请求数据
    request_data = {
        "url": rtmp_url,
        "url_type": 1,  # RTMP
        "video_id": video_id,
        "video_quality": video_quality,
    }

    # 构造完整的 MQTT 请求消息（模拟）
    tid = str(uuid.uuid4())
    full_request = {
        "bid": tid,
        "data": request_data,
        "tid": tid,
        "timestamp": int(time.time() * 1000),
        "method": "live_start_push",
    }

    # 打印发送的请求
    print_json_message("📤 发送 MQTT 请求 (live_start_push)", full_request, "blue")

    # 调用 SDK 开始直播
    try:
        result = caller.call("live_start_push", request_data)

        # 构造完整的 MQTT 响应消息（模拟）
        full_response = {
            "bid": tid,
            "data": result,
            "tid": tid,
            "timestamp": int(time.time() * 1000),
            "method": "live_start_push",
        }

        # 打印接收的响应
        print_json_message("📥 接收 MQTT 响应 (live_start_push)", full_response, "green")

        # 判定成功：data.result == 0
        if result.get("result") == 0:
            console.print("\n[bold green]✓ 直播推流已启动！[/bold green]")

            # 显示额外信息（如果有）
            output = result.get("output", {})
            if output:
                console.print(f"[dim]输出信息: {output}[/dim]")

            return video_id
        else:
            error_code = result.get("result", "unknown")
            error_msg = result.get("message", "无错误信息")
            console.print("\n[bold red]✗ 直播推流失败[/bold red]")
            console.print(f"[red]错误码: {error_code}[/red]")
            console.print(f"[red]错误信息: {error_msg}[/red]")
            return None

    except Exception as e:
        console.print(f"\n[bold red]✗ 请求异常: {e}[/bold red]")
        return None


def stop_live(caller, video_id: str) -> bool:
    """
    停止直播推流（带详细 MQTT 消息打印）

    Args:
        caller: 服务调用器
        video_id: 要停止的 video_id

    Returns:
        是否成功停止

    Example:
        >>> success = stop_live(caller, "1234567890ABC/88-0-0/normal-0")
        >>> if success:
        ...     print("直播已停止")
    """
    console.print("\n[bold cyan]========== 停止直播推流 ==========[/bold cyan]")
    console.print(f"[cyan]Video ID:[/cyan] {video_id}")

    # 构造请求数据
    request_data = {"video_id": video_id}

    # 构造完整的 MQTT 请求消息（模拟）
    tid = str(uuid.uuid4())
    full_request = {
        "bid": tid,
        "data": request_data,
        "tid": tid,
        "timestamp": int(time.time() * 1000),
        "method": "live_stop_push",
    }

    # 打印发送的请求
    print_json_message("📤 发送 MQTT 请求 (live_stop_push)", full_request, "blue")

    try:
        result = caller.call("live_stop_push", request_data)

        # 构造完整的 MQTT 响应消息（模拟）
        full_response = {
            "bid": tid,
            "data": result,
            "tid": tid,
            "timestamp": int(time.time() * 1000),
            "method": "live_stop_push",
        }

        # 打印接收的响应
        print_json_message("📥 接收 MQTT 响应 (live_stop_push)", full_response, "green")

        # 判定成功：data.result == 0
        if result.get("result") == 0:
            console.print("\n[bold green]✓ 直播推流已停止！[/bold green]")

            # 显示额外信息（如果有）
            output = result.get("output", {})
            if output:
                console.print(f"[dim]输出信息: {output}[/dim]")
            return True
        else:
            error_code = result.get("result", "unknown")
            error_msg = result.get("message", "无错误信息")
            console.print("\n[bold red]✗ 停止直播失败[/bold red]")
            console.print(f"[red]错误码: {error_code}[/red]")
            console.print(f"[red]错误信息: {error_msg}[/red]")
            return False

    except Exception as e:
        console.print(f"\n[bold red]✗ 请求异常: {e}[/bold red]")
        return False


def set_live_quality(caller, video_id: str, video_quality: int) -> bool:
    """
    设置直播清晰度（带详细 MQTT 消息打印）

    Args:
        caller: 服务调用器
        video_id: 直播视频流的 ID，格式为 {sn}/{camera_index}/{video_index}
        video_quality: 清晰度等级
            0 - 自适应
            1 - 流畅 (960x540, 512Kbps)
            2 - 标清 (1280x720, 1Mbps)
            3 - 高清 (1280x720, 1.5Mbps)
            4 - 超清 (1920x1080, 3Mbps)

    Returns:
        是否成功设置

    Example:
        >>> success = set_live_quality(caller, "1234567890ABC/88-0-0/normal-0", 4)
        >>> if success:
        ...     print("清晰度已设置为超清")
    """
    quality_names = {0: "自适应", 1: "流畅", 2: "标清", 3: "高清", 4: "超清"}
    quality_name = quality_names.get(video_quality, "未知")

    console.print("\n[bold cyan]========== 设置直播清晰度 ==========[/bold cyan]")
    console.print(f"[cyan]Video ID:[/cyan] {video_id}")
    console.print(f"[cyan]清晰度:[/cyan] {quality_name}")

    # 构造请求数据
    request_data = {"video_id": video_id, "video_quality": video_quality}

    # 构造完整的 MQTT 请求消息（模拟）
    tid = str(uuid.uuid4())
    full_request = {
        "bid": tid,
        "data": request_data,
        "tid": tid,
        "timestamp": int(time.time() * 1000),
        "method": "live_set_quality",
    }

    # 打印发送的请求
    print_json_message("📤 发送 MQTT 请求 (live_set_quality)", full_request, "blue")

    try:
        result = caller.call("live_set_quality", request_data)

        # 构造完整的 MQTT 响应消息（模拟）
        full_response = {
            "bid": tid,
            "data": result,
            "tid": tid,
            "timestamp": int(time.time() * 1000),
            "method": "live_set_quality",
        }

        # 打印接收的响应
        print_json_message("📥 接收 MQTT 响应 (live_set_quality)", full_response, "green")

        # 判定成功：data.result == 0
        if result.get("result") == 0:
            console.print(f"\n[bold green]✓ 清晰度已设置为 {quality_name}！[/bold green]")

            # 显示额外信息（如果有）
            output = result.get("output", {})
            if output:
                console.print(f"[dim]输出信息: {output}[/dim]")
            return True
        else:
            error_code = result.get("result", "unknown")
            error_msg = result.get("message", "无错误信息")
            console.print("\n[bold red]✗ 设置清晰度失败[/bold red]")
            console.print(f"[red]错误码: {error_code}[/red]")
            console.print(f"[red]错误信息: {error_msg}[/red]")
            return False

    except Exception as e:
        console.print(f"\n[bold red]✗ 请求异常: {e}[/bold red]")
        return False


def zoom_control_loop(mqtt_client, payload_index: str, camera_type: str = "zoom") -> bool:
    """
    键盘控制变焦循环

    使用方向键控制相机变焦，按 q 或 ESC 退出。

    Args:
        mqtt_client: MQTT 客户端
        payload_index: 相机负载索引
        camera_type: 相机类型（"zoom", "ir", "wide"）

    Returns:
        是否退出（True 表示用户按了 q 或 ESC）

    Example:
        >>> zoom_control_loop(mqtt, "88-0-0", camera_type="zoom")
        ========== 变焦控制模式 ==========
        使用方向键控制变焦：
          ↑ - 放大 (zoom in)
          ↓ - 缩小 (zoom out)
          q 或 ESC - 退出并停止直播
    """
    # 初始变焦倍数
    zoom_factor = 1.0
    zoom_step = 0.5  # 每次调整步长
    min_zoom = 1.0
    max_zoom = 112.0 if camera_type != "ir" else 20.0

    console.print("\n[bold cyan]========== 变焦控制模式 ==========[/bold cyan]")
    console.print("[yellow]使用方向键控制变焦：[/yellow]")
    console.print("  [green]↑[/green] - 放大 (zoom in)")
    console.print("  [green]↓[/green] - 缩小 (zoom out)")
    console.print("  [red]q[/red] 或 [red]ESC[/red] - 退出并停止直播")
    console.print(f"\n[dim]当前变焦: {zoom_factor}x (范围: {min_zoom}-{max_zoom}x)[/dim]\n")

    stop_flag = threading.Event()

    def keyboard_listener():
        """键盘监听线程"""
        nonlocal zoom_factor

        while not stop_flag.is_set():
            try:
                key = get_key()

                if key == "UP":
                    # 放大
                    new_zoom = min(zoom_factor + zoom_step, max_zoom)
                    if new_zoom != zoom_factor:
                        zoom_factor = new_zoom
                        console.print(
                            f"[cyan]↑[/cyan] 放大至 [bold green]{zoom_factor:.1f}x[/bold green]"
                        )
                        set_camera_zoom(mqtt_client, payload_index, zoom_factor, camera_type)
                    else:
                        console.print(f"[yellow]已达到最大变焦 ({max_zoom}x)[/yellow]")

                elif key == "DOWN":
                    # 缩小
                    new_zoom = max(zoom_factor - zoom_step, min_zoom)
                    if new_zoom != zoom_factor:
                        zoom_factor = new_zoom
                        console.print(
                            f"[cyan]↓[/cyan] 缩小至 [bold green]{zoom_factor:.1f}x[/bold green]"
                        )
                        set_camera_zoom(mqtt_client, payload_index, zoom_factor, camera_type)
                    else:
                        console.print(f"[yellow]已达到最小变焦 ({min_zoom}x)[/yellow]")

                elif key in ["q", "Q", "ESC"]:
                    console.print("\n[yellow]退出变焦控制模式[/yellow]")
                    stop_flag.set()
                    break

            except Exception as e:
                console.print(f"[red]键盘输入错误: {e}[/red]")
                time.sleep(0.1)

    # 启动键盘监听线程
    listener_thread = threading.Thread(target=keyboard_listener, daemon=True)
    listener_thread.start()

    # 等待用户退出
    stop_flag.wait()
    listener_thread.join(timeout=1)

    return True  # 返回 True 表示用户要求退出

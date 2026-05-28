from __future__ import annotations

from typing import Optional

from ..utils import build_video_id
from .common import call_live_service, console, print_output


def start_live(
    caller,
    mqtt_client,
    rtmp_url: str,
    video_index: str = "normal-0",
    video_quality: int = 0,
) -> Optional[str]:
    """开始直播推流（带详细 MQTT 消息打印）。"""
    console.print("\n[bold cyan]========== 开始直播推流 ==========[/bold cyan]")
    video_id = build_video_id(mqtt_client, video_index)
    console.print(f"[cyan]Video ID:[/cyan] {video_id}")
    console.print(f"[cyan]RTMP URL:[/cyan] {rtmp_url}")
    console.print(
        f"[cyan]视频质量:[/cyan] {['自适应', '流畅', '标清', '高清', '超清'][video_quality]}"
    )
    result = call_live_service(
        caller,
        "live_start_push",
        {"url": rtmp_url, "url_type": 1, "video_id": video_id, "video_quality": video_quality},
        "直播推流",
    )
    if result is None:
        return None
    console.print("\n[bold green]✓ 直播推流已启动！[/bold green]")
    print_output(result)
    return video_id


def stop_live(caller, video_id: str) -> bool:
    """停止直播推流（带详细 MQTT 消息打印）。"""
    console.print("\n[bold cyan]========== 停止直播推流 ==========[/bold cyan]")
    console.print(f"[cyan]Video ID:[/cyan] {video_id}")
    result = call_live_service(caller, "live_stop_push", {"video_id": video_id}, "停止直播")
    if result is None:
        return False
    console.print("\n[bold green]✓ 直播推流已停止！[/bold green]")
    print_output(result)
    return True

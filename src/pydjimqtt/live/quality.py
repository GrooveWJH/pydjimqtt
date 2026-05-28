from __future__ import annotations

from .common import call_live_service, console, print_output


def set_live_quality(caller, video_id: str, video_quality: int) -> bool:
    """设置直播清晰度（带详细 MQTT 消息打印）。"""
    quality_names = {0: "自适应", 1: "流畅", 2: "标清", 3: "高清", 4: "超清"}
    quality_name = quality_names.get(video_quality, "未知")
    console.print("\n[bold cyan]========== 设置直播清晰度 ==========[/bold cyan]")
    console.print(f"[cyan]Video ID:[/cyan] {video_id}")
    console.print(f"[cyan]清晰度:[/cyan] {quality_name}")
    result = call_live_service(
        caller,
        "live_set_quality",
        {"video_id": video_id, "video_quality": video_quality},
        "设置清晰度",
    )
    if result is None:
        return False
    console.print(f"\n[bold green]✓ 清晰度已设置为 {quality_name}！[/bold green]")
    print_output(result)
    return True

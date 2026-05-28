from __future__ import annotations

from ...core import ServiceCaller
from ..common import call_service, console


def enter_drc_mode(
    caller: ServiceCaller,
    mqtt_broker: dict,
    osd_frequency: int = 30,
    hsi_frequency: int = 10,
) -> dict:
    """进入 DRC 模式"""
    console.print("[bold cyan]进入 DRC 模式...[/bold cyan]")
    return call_service(
        caller,
        "drc_mode_enter",
        {
            "mqtt_broker": mqtt_broker,
            "osd_frequency": osd_frequency,
            "hsi_frequency": hsi_frequency,
        },
        f"已进入 DRC 模式 (OSD: {osd_frequency}Hz, HSI: {hsi_frequency}Hz)",
    )


def exit_drc_mode(caller: ServiceCaller) -> dict:
    """退出 DRC 模式"""
    console.print("[cyan]退出 DRC 模式...[/cyan]")
    return call_service(caller, "drc_mode_exit", success_msg="已退出 DRC 模式")


def change_live_lens(caller: ServiceCaller, video_id: str, video_type: str = "normal") -> dict:
    """切换直播镜头"""
    lens_names = {"normal": "默认", "thermal": "红外", "wide": "广角", "zoom": "变焦"}
    lens_name = lens_names.get(video_type, video_type)
    console.print(f"[cyan]切换直播镜头: {video_id} → {lens_name}[/cyan]")
    return call_service(
        caller,
        "live_lens_change",
        {"video_id": video_id, "video_type": video_type},
        f"镜头已切换到{lens_name}",
    )


def set_live_quality(caller: ServiceCaller, video_id: str, video_quality: int) -> dict:
    """设置直播清晰度"""
    quality_names = {0: "自适应", 1: "流畅", 2: "标清", 3: "高清", 4: "超清"}
    quality_name = quality_names.get(video_quality, "未知")
    console.print(f"[cyan]设置直播清晰度: {quality_name} (video_id: {video_id})[/cyan]")
    return call_service(
        caller,
        "live_set_quality",
        {"video_id": video_id, "video_quality": video_quality},
        f"清晰度已设置为 {quality_name}",
    )


def start_live_push(
    caller: ServiceCaller,
    url: str,
    video_id: str,
    url_type: int = 0,
    video_quality: int = 0,
) -> dict:
    """开始直播推流 (url_type: 0-RTMP, 1-RTSP, 2-GB28181)"""
    console.print("[bold cyan]开始直播推流...[/bold cyan]")
    console.print(f"[dim]URL: {url}[/dim]")
    console.print(f"[dim]镜头: {video_id}[/dim]")
    return call_service(
        caller,
        "live_start_push",
        {
            "url": url,
            "video_id": video_id,
            "url_type": url_type,
            "video_quality": video_quality,
        },
        "直播推流已开始",
    )


def stop_live_push(caller: ServiceCaller, video_id: str) -> dict:
    """停止直播推流"""
    console.print(f"[cyan]停止直播推流: {video_id}[/cyan]")
    return call_service(caller, "live_stop_push", {"video_id": video_id}, "直播推流已停止")

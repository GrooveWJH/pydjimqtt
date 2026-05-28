from __future__ import annotations

from ...core import MQTTClient
from .replies import console, next_seq, publish, wait_for_drc_reply


def drc_live_lens_change(
    mqtt_client: MQTTClient,
    payload_index: str,
    video_type: str,
    seq: int | None = None,
    debug_full_request: bool = False,
) -> None:
    """发送 DRC 直播镜头切换指令（Fire-and-forget）"""
    if not payload_index:
        console.print("[red]✗ payload_index 不能为空[/red]")
        raise ValueError("payload_index must be a non-empty string")

    normalized_video_type = str(video_type or "").strip().lower()
    if normalized_video_type == "ir":
        normalized_video_type = "thermal"
    if normalized_video_type not in ("wide", "zoom", "thermal"):
        raise ValueError(
            f"video_type must be one of ['wide', 'zoom', 'thermal'], got {video_type!r}"
        )

    payload = {
        "seq": next_seq() if seq is None else seq,
        "method": "drc_live_lens_change",
        "data": {"payload_index": payload_index, "video_type": normalized_video_type},
    }
    try:
        if debug_full_request:
            from ...utils import print_json_message

            print_json_message(
                "📤 发送 MQTT 请求 (drc_live_lens_change)",
                {
                    "topic": f"thing/product/{mqtt_client.gateway_sn}/drc/down",
                    "qos": 0,
                    "payload": payload,
                },
                "blue",
            )
        publish(mqtt_client, payload)
        console.print(
            f"[cyan]→[/cyan] 镜头切换指令已发送: {normalized_video_type} (payload: {payload_index})"
        )
    except Exception as exc:
        console.print(f"[red]✗ 镜头切换指令发送失败: {exc}[/red]")
        raise


def drc_live_lens_change_wait(
    mqtt_client: MQTTClient,
    payload_index: str,
    video_type: str,
    timeout: float = 3.0,
    seq: int | None = None,
    debug_full_request: bool = False,
) -> dict:
    """发送 DRC 直播镜头切换并等待 drc/up 回包。"""
    seq = next_seq() if seq is None else seq
    return wait_for_drc_reply(
        mqtt_client,
        method="drc_live_lens_change",
        seq=seq,
        timeout=timeout,
        send_fn=lambda: drc_live_lens_change(
            mqtt_client,
            payload_index=payload_index,
            video_type=video_type,
            seq=seq,
            debug_full_request=debug_full_request,
        ),
    )

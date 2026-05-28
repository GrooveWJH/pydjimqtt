from __future__ import annotations

from ...core import MQTTClient
from .replies import console, next_seq, publish, wait_for_drc_reply


def set_camera_zoom(
    mqtt_client: MQTTClient,
    payload_index: str,
    zoom_factor: float,
    camera_type: str = "zoom",
    seq: int | None = None,
    debug_full_request: bool = False,
) -> None:
    """发送相机变焦控制指令（单次发送，Fire-and-forget）"""
    if camera_type not in ["ir", "wide", "zoom"]:
        console.print(f"[red]✗ 无效的相机类型: {camera_type} (应为 'ir', 'wide', 或 'zoom')[/red]")
        raise ValueError(f"camera_type must be one of ['ir', 'wide', 'zoom'], got {camera_type}")
    if not 1 <= zoom_factor <= 112:
        console.print(f"[red]✗ 变焦倍数超出范围: {zoom_factor} (应在 1-112)[/red]")
        raise ValueError(f"zoom_factor must be in range [1, 112], got {zoom_factor}")

    payload = {
        "seq": next_seq() if seq is None else seq,
        "method": "drc_camera_focal_length_set",
        "data": {
            "payload_index": payload_index,
            "camera_type": camera_type,
            "zoom_factor": zoom_factor,
        },
    }
    try:
        if debug_full_request:
            from ...utils import print_json_message

            print_json_message(
                "📤 发送 MQTT 请求 (drc_camera_focal_length_set)",
                {
                    "topic": f"thing/product/{mqtt_client.gateway_sn}/drc/down",
                    "qos": 0,
                    "payload": payload,
                },
                "blue",
            )
        publish(mqtt_client, payload)
        console.print(
            f"[cyan]→[/cyan] 变焦指令已发送: {camera_type} zoom={zoom_factor}x (payload: {payload_index})"
        )
    except Exception as exc:
        console.print(f"[red]✗ 变焦控制发送失败: {exc}[/red]")
        raise


def camera_screen_split(
    mqtt_client: MQTTClient,
    payload_index: str,
    enable: bool,
    seq: int | None = None,
) -> None:
    """发送分屏控制指令（单次发送，Fire-and-forget）"""
    if not payload_index:
        console.print("[red]✗ payload_index 不能为空[/red]")
        raise ValueError("payload_index must be a non-empty string")

    payload = {
        "seq": next_seq() if seq is None else seq,
        "method": "drc_camera_screen_split",
        "data": {"payload_index": payload_index, "enable": bool(enable)},
    }
    try:
        publish(mqtt_client, payload)
        status = "开启" if enable else "关闭"
        console.print(f"[cyan]→[/cyan] 分屏指令已发送: {status} (payload: {payload_index})")
    except Exception as exc:
        console.print(f"[red]✗ 分屏指令发送失败: {exc}[/red]")
        raise


def camera_screen_split_wait(
    mqtt_client: MQTTClient,
    payload_index: str,
    enable: bool,
    timeout: float = 3.0,
    seq: int | None = None,
) -> dict:
    """发送分屏控制指令并等待 drc/up 回包。"""
    seq = next_seq() if seq is None else seq
    return wait_for_drc_reply(
        mqtt_client,
        method="drc_camera_screen_split",
        seq=seq,
        timeout=timeout,
        send_fn=lambda: camera_screen_split(
            mqtt_client, payload_index=payload_index, enable=enable, seq=seq
        ),
    )

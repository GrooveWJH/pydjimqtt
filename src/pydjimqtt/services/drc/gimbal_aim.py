from __future__ import annotations

from ...core import MQTTClient
from .replies import console, next_seq, publish


def camera_look_at(
    mqtt_client: MQTTClient,
    payload_index: str,
    latitude: float,
    longitude: float,
    height: float,
    locked: bool = False,
    seq: int | None = None,
) -> None:
    """发送相机 Look At 指令（云台指向目标点，Fire-and-forget）"""
    if not -90 <= latitude <= 90:
        console.print(f"[red]✗ 纬度超出范围: {latitude} (应在 -90 ~ 90)[/red]")
        raise ValueError(f"latitude must be in range [-90, 90], got {latitude}")
    if not -180 <= longitude <= 180:
        console.print(f"[red]✗ 经度超出范围: {longitude} (应在 -180 ~ 180)[/red]")
        raise ValueError(f"longitude must be in range [-180, 180], got {longitude}")
    if not -1000 <= height <= 10000:
        console.print(f"[red]✗ 高度超出合理范围: {height} (建议 -1000 ~ 10000)[/red]")

    payload = {
        "seq": next_seq() if seq is None else seq,
        "method": "drc_camera_look_at",
        "data": {
            "payload_index": payload_index,
            "locked": locked,
            "latitude": latitude,
            "longitude": longitude,
            "height": height,
        },
    }
    try:
        publish(mqtt_client, payload)
        console.print(
            f"[cyan]→[/cyan] Look At 指令已发送: "
            f"lat={latitude:.6f}, lon={longitude:.6f}, h={height:.1f}m "
            f"(locked={locked}, payload: {payload_index})"
        )
    except Exception as exc:
        console.print(f"[red]✗ Look At 控制发送失败: {exc}[/red]")
        raise


def camera_aim(
    mqtt_client: MQTTClient,
    payload_index: str,
    x: float,
    y: float,
    camera_type: str = "zoom",
    locked: bool = False,
    seq: int | None = None,
) -> None:
    """发送相机 AIM 指令（双击镜头目标点，使其成为视野中心，Fire-and-forget）"""
    if not 0 <= x <= 1:
        console.print(f"[red]✗ x 坐标超出范围: {x} (应在 0-1)[/red]")
        raise ValueError(f"x must be in range [0, 1], got {x}")
    if not 0 <= y <= 1:
        console.print(f"[red]✗ y 坐标超出范围: {y} (应在 0-1)[/red]")
        raise ValueError(f"y must be in range [0, 1], got {y}")
    if camera_type not in ["ir", "wide", "zoom"]:
        console.print(f"[red]✗ 无效的相机类型: {camera_type} (应为 'ir', 'wide', 或 'zoom')[/red]")
        raise ValueError(f"camera_type must be one of ['ir', 'wide', 'zoom'], got {camera_type}")

    payload = {
        "seq": next_seq() if seq is None else seq,
        "method": "drc_camera_aim",
        "data": {
            "payload_index": payload_index,
            "camera_type": camera_type,
            "locked": locked,
            "x": x,
            "y": y,
        },
    }
    try:
        publish(mqtt_client, payload)
        console.print(
            f"[cyan]→[/cyan] AIM 指令已发送: "
            f"x={x:.2f}, y={y:.2f}, camera={camera_type} "
            f"(locked={locked}, payload: {payload_index})"
        )
    except Exception as exc:
        console.print(f"[red]✗ AIM 控制发送失败: {exc}[/red]")
        raise

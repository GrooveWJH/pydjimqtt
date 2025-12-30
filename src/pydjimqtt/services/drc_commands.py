"""
DRC 无回包指令（Fire-and-forget 模式）

这些指令与普通服务不同：
- 使用 /drc/down topic（而非 /services）
- QoS 0，无响应回包
- 使用 seq 序列号（而非 tid）
- 调用方负责控制发送频率
"""
import json
import time
import threading
from ..core import MQTTClient
from rich.console import Console

console = Console()


def send_stick_control(
    mqtt_client: MQTTClient,
    roll: int = 1024,
    pitch: int = 1024,
    throttle: int = 1024,
    yaw: int = 1024,
    seq: int | None = None
) -> None:
    """
    发送 DRC 杆量控制指令（单次发送，调用方控制频率）

    Args:
        mqtt_client: MQTT 客户端
        roll: 横滚/左右平移 (364-1684, 中值1024)
        pitch: 俯仰/前后平移 (364-1684, 中值1024)
        throttle: 升降 (364-1684, 中值1024)
        yaw: 偏航/旋转 (364-1684, 中值1024)
        seq: 序列号（None 则自动生成时间戳）

    注意:
        - 无返回值（Fire-and-forget）
        - 调用方需自行控制频率（推荐 5-10Hz / 100-200ms 间隔）
        - 参数范围：364-1684，中值 1024（悬停/静止）

    示例:
        >>> # 单次发送
        >>> send_stick_control(mqtt, roll=1200, pitch=1024, yaw=1024, throttle=1024)
        >>>
        >>> # 循环控制（调用方负责频率）
        >>> for i in range(50):
        ...     send_stick_control(mqtt, roll=1200, pitch=1024, yaw=1024, throttle=1024)
        ...     time.sleep(0.1)  # 10Hz
    """
    # 参数校验
    for name, value in [("roll", roll), ("pitch", pitch), ("throttle", throttle), ("yaw", yaw)]:
        if not 364 <= value <= 1684:
            console.print(f"[red]✗ {name} 超出范围: {value} (应在 364-1684)[/red]")
            raise ValueError(f"{name} must be in range [364, 1684], got {value}")

    # 生成 seq
    if seq is None:
        seq = int(time.time() * 1000)

    # 构建消息
    topic = f"thing/product/{mqtt_client.gateway_sn}/drc/down"
    payload = {
        "seq": seq,
        "method": "stick_control",
        "data": {
            "roll": roll,
            "pitch": pitch,
            "throttle": throttle,
            "yaw": yaw
        }
    }

    # 发送（QoS 0，无响应）
    try:
        mqtt_client.client.publish(topic, json.dumps(payload), qos=0)
    except Exception as e:
        console.print(f"[red]✗ 杆量控制发送失败: {e}[/red]")
        raise


def set_camera_zoom(
    mqtt_client: MQTTClient,
    payload_index: str,
    zoom_factor: float,
    camera_type: str = "zoom",
    seq: int | None = None
) -> None:
    """
    发送相机变焦控制指令（单次发送，Fire-and-forget）

    Args:
        mqtt_client: MQTT 客户端
        payload_index: 相机枚举值（格式: {type-subtype-gimbalindex}，如 "88-0-0"）
        zoom_factor: 变焦倍数（可见光: 1-112，红外: 2-20）
        camera_type: 相机类型（"ir"=红外, "wide"=广角, "zoom"=变焦，默认 "zoom"）
        seq: 序列号（None 则自动生成时间戳）

    注意:
        - 无返回值（Fire-and-forget）
        - 可见光相机变焦范围: 1-112
        - 红外相机变焦范围: 2-20

    示例:
        >>> # 设置变焦倍数为 10
        >>> set_camera_zoom(mqtt, payload_index="88-0-0", zoom_factor=10)
        >>>
        >>> # 设置红外相机变焦
        >>> set_camera_zoom(mqtt, payload_index="88-0-0", zoom_factor=5, camera_type="ir")
    """
    # 参数校验
    if camera_type not in ["ir", "wide", "zoom"]:
        console.print(f"[red]✗ 无效的相机类型: {camera_type} (应为 'ir', 'wide', 或 'zoom')[/red]")
        raise ValueError(f"camera_type must be one of ['ir', 'wide', 'zoom'], got {camera_type}")

    # 变焦倍数范围检查
    if camera_type == "ir":
        if not 2 <= zoom_factor <= 20:
            console.print(f"[red]✗ 红外相机变焦倍数超出范围: {zoom_factor} (应在 2-20)[/red]")
            raise ValueError(f"For IR camera, zoom_factor must be in range [2, 20], got {zoom_factor}")
    else:  # zoom 或 wide
        if not 1 <= zoom_factor <= 112:
            console.print(f"[red]✗ 可见光相机变焦倍数超出范围: {zoom_factor} (应在 1-112)[/red]")
            raise ValueError(f"For visible camera, zoom_factor must be in range [1, 112], got {zoom_factor}")

    # 生成 seq
    if seq is None:
        seq = int(time.time() * 1000)

    # 构建消息
    topic = f"thing/product/{mqtt_client.gateway_sn}/drc/down"
    payload = {
        "seq": seq,
        "method": "drc_camera_focal_length_set",
        "data": {
            "payload_index": payload_index,
            "camera_type": camera_type,
            "zoom_factor": zoom_factor
        }
    }

    # 发送（QoS 0，无响应）
    try:
        mqtt_client.client.publish(topic, json.dumps(payload), qos=0)
        console.print(f"[cyan]→[/cyan] 变焦指令已发送: {camera_type} zoom={zoom_factor}x (payload: {payload_index})")
    except Exception as e:
        console.print(f"[red]✗ 变焦控制发送失败: {e}[/red]")
        raise


def take_photo(
    mqtt_client: MQTTClient,
    payload_index: str,
    seq: int | None = None
) -> None:
    """
    发送拍照指令（单次发送，Fire-and-forget）

    Args:
        mqtt_client: MQTT 客户端
        payload_index: 相机枚举值（格式: {type-subtype-gimbalindex}，如 "89-0-0"）
        seq: 序列号（None 则自动生成时间戳）

    注意:
        - 无返回值（Fire-and-forget）
        - 响应会通过 drc/up 上报 method: drc_camera_photo_take
    """
    if not payload_index:
        console.print("[red]✗ payload_index 不能为空[/red]")
        raise ValueError("payload_index must be a non-empty string")

    if seq is None:
        seq = int(time.time() * 1000)

    topic = f"thing/product/{mqtt_client.gateway_sn}/drc/down"
    payload = {
        "seq": seq,
        "method": "drc_camera_photo_take",
        "data": {
            "payload_index": payload_index
        }
    }

    try:
        mqtt_client.client.publish(topic, json.dumps(payload), qos=0)
        console.print(f"[cyan]→[/cyan] 拍照指令已发送 (payload: {payload_index})")
    except Exception as e:
        console.print(f"[red]✗ 拍照指令发送失败: {e}[/red]")
        raise


def take_photo_wait(
    mqtt_client: MQTTClient,
    payload_index: str,
    timeout: float = 10.0,
    seq: int | None = None
) -> dict:
    """
    发送拍照指令并等待结果回包。

    Returns:
        {'ok': bool, 'result': int | None, 'status': str | None, 'seq': int}
    """
    if not mqtt_client.client:
        raise RuntimeError("MQTT client is not connected")

    if seq is None:
        seq = int(time.time() * 1000)

    result_box: dict = {"result": None, "status": None}
    done = threading.Event()
    original_on_message = mqtt_client.client.on_message

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except Exception:
            payload = {}
        if payload.get("method") == "drc_camera_photo_take" and payload.get("seq") == seq:
            data = payload.get("data", {})
            result_box["result"] = data.get("result")
            result_box["status"] = data.get("status")
            done.set()
        if original_on_message:
            original_on_message(client, userdata, msg)

    mqtt_client.client.on_message = on_message
    try:
        take_photo(mqtt_client, payload_index=payload_index, seq=seq)
        if not done.wait(timeout):
            raise TimeoutError("drc_camera_photo_take timeout")
    finally:
        mqtt_client.client.on_message = original_on_message

    result = result_box.get("result")
    return {
        "ok": result == 0,
        "result": result,
        "status": result_box.get("status"),
        "seq": seq,
    }


def camera_look_at(
    mqtt_client: MQTTClient,
    payload_index: str,
    latitude: float,
    longitude: float,
    height: float,
    locked: bool = False,
    seq: int | None = None
) -> None:
    """
    发送相机 Look At 指令（云台指向目标点，Fire-and-forget）

    飞行器将从当前朝向转向实际经纬高度指定的点。

    Args:
        mqtt_client: MQTT 客户端
        payload_index: 相机枚举值（格式: {type-subtype-gimbalindex}，如 "89-0-0"）
        latitude: 目标点纬度（角度值，-90 ~ 90，南纬负，北纬正）
        longitude: 目标点经度（角度值，-180 ~ 180，东经正，西经负）
        height: 目标点高度（椭球高，单位：米，2-10000）
        locked: 机头和云台的相对关系是否锁定
                False: 仅云台转，机身不转（推荐用于 M30/M30T）
                True: 锁定机头，云台和机身一起转
        seq: 序列号（None 则自动生成时间戳）

    注意:
        - 无返回值（Fire-and-forget）
        - M30/M30T 建议使用 locked=False（仅云台转）
        - 云台限位角后 lookat 功能可能异常
        - 纬度精度到小数点后6位
        - 经度精度到小数点后6位

    示例:
        >>> # 让云台看向地面（使用无人机当前位置，高度-100米）
        >>> lat, lon, _ = mqtt.get_position()
        >>> camera_look_at(mqtt, payload_index="89-0-0",
        ...                latitude=lat, longitude=lon, height=-100, locked=False)
        >>>
        >>> # 让云台看向指定点
        >>> camera_look_at(mqtt, payload_index="89-0-0",
        ...                latitude=22.908061, longitude=113.705107,
        ...                height=24.84, locked=False)
    """
    # 参数校验
    if not -90 <= latitude <= 90:
        console.print(f"[red]✗ 纬度超出范围: {latitude} (应在 -90 ~ 90)[/red]")
        raise ValueError(f"latitude must be in range [-90, 90], got {latitude}")

    if not -180 <= longitude <= 180:
        console.print(f"[red]✗ 经度超出范围: {longitude} (应在 -180 ~ 180)[/red]")
        raise ValueError(f"longitude must be in range [-180, 180], got {longitude}")

    if not -1000 <= height <= 10000:
        console.print(f"[red]✗ 高度超出合理范围: {height} (建议 -1000 ~ 10000)[/red]")
        # 仅警告，不抛出异常（允许负高度用于看地面）

    # 生成 seq
    if seq is None:
        seq = int(time.time() * 1000)

    # 构建消息
    topic = f"thing/product/{mqtt_client.gateway_sn}/drc/down"
    payload = {
        "seq": seq,
        "method": "drc_camera_look_at",
        "data": {
            "payload_index": payload_index,
            "locked": locked,
            "latitude": latitude,
            "longitude": longitude,
            "height": height
        }
    }

    # 发送（QoS 0，无响应）
    try:
        mqtt_client.client.publish(topic, json.dumps(payload), qos=0)
        console.print(
            f"[cyan]→[/cyan] Look At 指令已发送: "
            f"lat={latitude:.6f}, lon={longitude:.6f}, h={height:.1f}m "
            f"(locked={locked}, payload: {payload_index})"
        )
    except Exception as e:
        console.print(f"[red]✗ Look At 控制发送失败: {e}[/red]")
        raise


def camera_aim(
    mqtt_client: MQTTClient,
    payload_index: str,
    x: float,
    y: float,
    camera_type: str = "zoom",
    locked: bool = False,
    seq: int | None = None
) -> None:
    """
    发送相机 AIM 指令（双击镜头目标点，使其成为视野中心，Fire-and-forget）

    在相机镜头的视野范围内，双击镜头中的目标点，该目标点将成为镜头视野的中心。

    Args:
        mqtt_client: MQTT 客户端
        payload_index: 相机枚举值（格式: {type-subtype-gimbalindex}，如 "89-0-0"）
        x: 目标坐标 x（0-1，以镜头左上角为坐标中心点，水平方向为 x）
        y: 目标坐标 y（0-1，以镜头左上角为坐标中心点，竖直方向为 y）
        camera_type: 相机类型（"ir"=红外, "wide"=广角, "zoom"=变焦，默认 "zoom"）
        locked: 机头和云台的相对关系是否锁定
                False: 仅云台转，机身不转
                True: 锁定机头，云台和机身一起转
        seq: 序列号（None 则自动生成时间戳）

    注意:
        - 无返回值（Fire-and-forget）
        - x, y 取值范围 0-1
        - (0.5, 0.5) 表示视野中心
        - (0.5, 1.0) 表示视野底部中心（云台往下）

    示例:
        >>> # AIM 到视野中心（无效果，已经在中心）
        >>> camera_aim(mqtt, payload_index="89-0-0", x=0.5, y=0.5)
        >>>
        >>> # AIM 到正下方（云台往下）
        >>> camera_aim(mqtt, payload_index="89-0-0", x=0.5, y=1.0, camera_type="zoom")
        >>>
        >>> # AIM 到视野右下角
        >>> camera_aim(mqtt, payload_index="89-0-0", x=0.8, y=0.8)
    """
    # 参数校验
    if not 0 <= x <= 1:
        console.print(f"[red]✗ x 坐标超出范围: {x} (应在 0-1)[/red]")
        raise ValueError(f"x must be in range [0, 1], got {x}")

    if not 0 <= y <= 1:
        console.print(f"[red]✗ y 坐标超出范围: {y} (应在 0-1)[/red]")
        raise ValueError(f"y must be in range [0, 1], got {y}")

    if camera_type not in ["ir", "wide", "zoom"]:
        console.print(f"[red]✗ 无效的相机类型: {camera_type} (应为 'ir', 'wide', 或 'zoom')[/red]")
        raise ValueError(f"camera_type must be one of ['ir', 'wide', 'zoom'], got {camera_type}")

    # 生成 seq
    if seq is None:
        seq = int(time.time() * 1000)

    # 构建消息
    topic = f"thing/product/{mqtt_client.gateway_sn}/drc/down"
    payload = {
        "seq": seq,
        "method": "drc_camera_aim",
        "data": {
            "payload_index": payload_index,
            "camera_type": camera_type,
            "locked": locked,
            "x": x,
            "y": y
        }
    }

    # 发送（QoS 0，无响应）
    try:
        mqtt_client.client.publish(topic, json.dumps(payload), qos=0)
        console.print(
            f"[cyan]→[/cyan] AIM 指令已发送: "
            f"x={x:.2f}, y={y:.2f}, camera={camera_type} "
            f"(locked={locked}, payload: {payload_index})"
        )
    except Exception as e:
        console.print(f"[red]✗ AIM 控制发送失败: {e}[/red]")
        raise

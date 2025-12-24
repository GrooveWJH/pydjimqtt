"""
杆量控制原语
"""
import time
from ..services import send_stick_control
from ..core import MQTTClient


def send_stick_repeatedly(
    mqtt: MQTTClient,
    roll: int = 1024,
    pitch: int = 1024,
    throttle: int = 1024,
    yaw: int = 1024,
    duration: float = 1.0,
    frequency: float = 10.0
) -> None:
    """
    重复发送杆量控制指令

    Args:
        mqtt: MQTT客户端
        roll: 横滚通道值
        pitch: 俯仰通道值
        throttle: 油门通道值
        yaw: 偏航通道值
        duration: 持续时间（秒）
        frequency: 发送频率（Hz）

    Example:
        >>> # 解锁：发送中值1秒
        >>> send_stick_repeatedly(mqtt, duration=1.0, frequency=10)
        >>> # 悬停：发送中值5秒
        >>> send_stick_repeatedly(mqtt, duration=5.0, frequency=10)
    """
    interval = 1.0 / frequency
    count = int(duration * frequency)
    for _ in range(count):
        send_stick_control(mqtt, roll=roll, pitch=pitch, throttle=throttle, yaw=yaw)
        time.sleep(interval)

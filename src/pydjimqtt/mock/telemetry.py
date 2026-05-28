from __future__ import annotations

import math
import time
from typing import Optional

MODE_NAMES = {
    0: "待机",
    1: "起飞准备",
    2: "起飞准备完毕",
    3: "摇杆控制",
    4: "自动起飞",
    5: "航线飞行",
    6: "全景拍照",
    7: "智能跟随",
    8: "ADS-B 躲避",
    9: "自动返航",
    10: "自动降落",
    11: "强制降落",
    12: "三桨叶降落",
    13: "升级中",
    14: "未连接",
    15: "APAS",
    16: "虚拟摇杆状态",
    17: "指令飞行",
}


class MockTelemetry:
    def __init__(self, index: int, base_height: float = 50.0) -> None:
        self.start_time = time.time()
        self.phase_offset = index * (2 * math.pi / 5)
        self.base_lat = 22.5380 + index * 0.001
        self.base_lon = 113.9380 + index * 0.001
        self.base_height = base_height
        self.flight_radius = 0.0005
        self.angular_velocity = 0.1
        self.vertical_amplitude = 5.0
        self.vertical_frequency = 0.05

    def elapsed(self) -> float:
        return time.time() - self.start_time

    def position(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        t = self.elapsed()
        angle = self.angular_velocity * t + self.phase_offset
        lat = self.base_lat + self.flight_radius * math.sin(angle)
        lon = self.base_lon + self.flight_radius * math.cos(angle)
        height = (
            self.base_height
            + 20.0
            + self.vertical_amplitude * math.sin(self.vertical_frequency * t)
        )
        return (lat, lon, height)

    def speed(self) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        t = self.elapsed()
        angle = self.angular_velocity * t + self.phase_offset
        tangential_velocity = self.flight_radius * self.angular_velocity * 111000
        speed_x = tangential_velocity * math.cos(angle)
        speed_y = -tangential_velocity * math.sin(angle)
        speed_z = (
            self.vertical_amplitude
            * self.vertical_frequency
            * math.cos(self.vertical_frequency * t)
        )
        return (math.sqrt(speed_x**2 + speed_y**2), speed_x, speed_y, speed_z)

    def attitude_head(self) -> Optional[float]:
        return math.degrees(self.angular_velocity * self.elapsed() + self.phase_offset) % 360

    def battery_percent(self) -> Optional[int]:
        elapsed_minutes = self.elapsed() / 60.0
        return max(20, 100 - int(elapsed_minutes))

    def flight_mode(self) -> Optional[int]:
        modes = [0, 3, 16, 9, 3, 0]
        return modes[int(self.elapsed() / 30) % len(modes)]

    def gimbal_attitude(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        t = self.elapsed()
        return (10.0 * math.sin(0.1 * t), 0.0, 45.0 * math.sin(0.05 * t))

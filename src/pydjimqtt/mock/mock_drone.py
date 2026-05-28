from __future__ import annotations

from typing import Any, Optional

from .heartbeat import MockHeartbeatThread
from .service_caller import MockServiceCaller
from .telemetry import MODE_NAMES, MockTelemetry


class MockMQTTClient:
    """模拟的 MQTT 客户端，接口与真实 MQTTClient 保持一致。"""

    def __init__(self, gateway_sn: str, mqtt_config: dict[str, Any], index: int = 0):
        self.gateway_sn = gateway_sn
        self.config = mqtt_config
        self.client = self
        self._connected = False
        self.telemetry = MockTelemetry(index)
        self.takeoff_height = self.telemetry.base_height

    def connect(self):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def _elapsed(self) -> float:
        return self.telemetry.elapsed()

    def get_position(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        return self.telemetry.position()

    def get_latitude(self) -> Optional[float]:
        lat, _, _ = self.get_position()
        return lat

    def get_longitude(self) -> Optional[float]:
        _, lon, _ = self.get_position()
        return lon

    def get_height(self) -> Optional[float]:
        _, _, height = self.get_position()
        return height

    def get_relative_height(self) -> Optional[float]:
        _, _, height = self.get_position()
        if height is not None and self.takeoff_height is not None:
            return height - self.takeoff_height
        return None

    def get_speed(
        self,
    ) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        return self.telemetry.speed()

    def get_attitude_head(self) -> Optional[float]:
        return self.telemetry.attitude_head()

    def get_local_height(self) -> Optional[float]:
        rel_height = self.get_relative_height()
        return rel_height * 100 if rel_height is not None else None

    def is_local_height_ok(self) -> bool:
        return True

    def get_battery_percent(self) -> Optional[int]:
        return self.telemetry.battery_percent()

    def get_flight_mode(self) -> Optional[int]:
        return self.telemetry.flight_mode()

    def get_flight_mode_name(self) -> str:
        mode_code = self.get_flight_mode()
        if mode_code is None:
            return "未知"
        return MODE_NAMES.get(mode_code, f"未知模式({mode_code})")

    def get_drone_state(self) -> dict[str, Any]:
        return {
            "mode_code": self.get_flight_mode(),
            "rth_altitude": 100,
            "distance_limit": 5000,
            "height_limit": 420,
            "is_in_fixed_speed": False,
            "night_lights_state": 0,
        }

    def get_aircraft_sn(self) -> Optional[str]:
        return f"AIRCRAFT_{self.gateway_sn[-6:]}"

    def get_topo_data(self) -> Optional[dict[str, Any]]:
        return {
            "domain": "2",
            "type": 174,
            "sub_type": 0,
            "device_secret": "mock_secret",
            "nonce": "mock_nonce",
            "thing_version": "1.2.0",
            "sub_devices": [
                {
                    "sn": f"AIRCRAFT_{self.gateway_sn[-6:]}",
                    "domain": "0",
                    "type": 99,
                    "sub_type": 0,
                    "index": "A",
                    "device_secret": "mock_aircraft_secret",
                    "nonce": "mock_aircraft_nonce",
                    "thing_version": "1.2.0",
                }
            ],
        }

    def get_payload_index(self) -> Optional[str]:
        return "88-0-0"

    def get_gimbal_attitude(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        return self.telemetry.gimbal_attitude()

    def get_camera_osd_data(self) -> dict[str, Any]:
        pitch, roll, yaw = self.get_gimbal_attitude()
        return {
            "payload_index": self.get_payload_index(),
            "gimbal_pitch": pitch,
            "gimbal_roll": roll,
            "gimbal_yaw": yaw,
        }

    def publish(self, topic: str, payload: str, qos: int = 0):
        pass

    def cleanup_request(self, tid: str):
        pass

    def get_osd_frequency(self) -> float:
        return 100.0

    def is_online(self, timeout: float = 2.0) -> bool:
        return True


def create_mock_connections(uav_configs: list) -> list:
    """创建多个模拟连接。"""
    connections = []
    for index, config in enumerate(uav_configs):
        mqtt = MockMQTTClient(config["sn"], mqtt_config={}, index=index)
        mqtt.connect()
        connections.append((mqtt, MockServiceCaller(mqtt), MockHeartbeatThread()))
    return connections


__all__ = [
    "MockMQTTClient",
    "MockServiceCaller",
    "MockHeartbeatThread",
    "create_mock_connections",
]

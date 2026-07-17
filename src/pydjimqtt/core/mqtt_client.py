"""
MQTT 客户端 - 负责连接管理和消息收发
"""

import threading
from typing import Any, Optional

import paho.mqtt.client as mqtt
from rich.console import Console

from .client_views import (
    MODE_NAMES,
    get_aircraft_sn,
    get_around_distances,
    get_connection_diagnostics,
    get_hsi_data,
    get_osd_frequency,
    get_osd_timing_diagnostics,
    is_online,
    wait_for_gimbal_attitude,
)
from .flyto_events import wait_for_flyto_event
from .message_handlers import handle_message
from .publisher import publish as publish_service
from .state import initialize_client_state

console = Console()


class MQTTClient:
    """简单的 MQTT 客户端封装。"""

    def __init__(self, gateway_sn: str, mqtt_config: dict[str, Any]):
        self.gateway_sn = gateway_sn
        self.config = mqtt_config
        self.lock = threading.Lock()
        initialize_client_state(self, mqtt.Client)

    def connect(self):
        """建立 MQTT 连接"""
        # 添加3位随机UUID后缀，避免多个客户端冲突
        import uuid

        random_suffix = str(uuid.uuid4())[:3]
        client_id = f"python-drc-{self.gateway_sn}-{random_suffix}"

        self.client = mqtt.Client(client_id=client_id)
        self.client.username_pw_set(self.config["username"], self.config["password"])
        self.client.on_message = self._on_message

        # 添加连接回调用于调试
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                console.print(f"[green]✓[/green] MQTT 连接成功 (rc={rc})")
            else:
                error_messages = {
                    1: "协议版本不正确",
                    2: "客户端 ID 无效",
                    3: "服务器不可用",
                    4: "用户名或密码错误",
                    5: "未授权",
                }
                error_msg = error_messages.get(rc, f"未知错误 (rc={rc})")
                console.print(f"[red]✗[/red] MQTT 连接失败: {error_msg}")

        def on_disconnect(client, userdata, rc):
            with self.lock:
                self._last_disconnect_rc = int(rc)
                self._last_disconnect_at = time.time()
                self._mqtt_disconnect_count += 1
            if rc != 0:
                console.print(f"[yellow]MQTT 非正常断开 (rc={rc})[/yellow]")

        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect

        console.print(f"[cyan]连接 MQTT: {self.config['host']}:{self.config['port']}[/cyan]")

        try:
            # 添加连接超时（5秒）
            self.client.connect(self.config["host"], self.config["port"], 60)
            self.client.loop_start()

            # 等待连接成功（最多等待 5 秒）
            import time

            timeout = 5
            start_time = time.time()
            while not self.client.is_connected():
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"MQTT 连接超时（{timeout}秒）")
                time.sleep(0.1)

        except Exception as e:
            console.print(f"[red]✗[/red] MQTT 连接异常: {e}")
            raise

        if self._is_virtual_gateway():
            console.print(
                "[yellow]⚠[/yellow] 虚拟网关模式：跳过默认产品主题订阅，等待上层自定义订阅"
            )
            return

        # 订阅响应主题
        reply_topic = f"thing/product/{self.gateway_sn}/services_reply"
        self.client.subscribe(reply_topic, qos=1)
        console.print(f"[green]✓[/green] 已订阅: {reply_topic}")

        # 订阅 DRC 上行主题（接收 OSD/HSI 数据）
        drc_up_topic = f"thing/product/{self.gateway_sn}/drc/up"
        self.client.subscribe(drc_up_topic, qos=0)
        console.print(f"[green]✓[/green] 已订阅: {drc_up_topic}")

        # 订阅设备状态主题（接收 update_topo 数据）
        status_topic = f"sys/product/{self.gateway_sn}/status"
        self.client.subscribe(status_topic, qos=0)
        console.print(f"[green]✓[/green] 已订阅: {status_topic}")

        # 订阅事件主题（接收 fly_to_point_progress 等事件）
        events_topic = f"thing/product/{self.gateway_sn}/events"
        self.client.subscribe(events_topic, qos=0)
        console.print(f"[green]✓[/green] 已订阅: {events_topic}")

    def _is_virtual_gateway(self) -> bool:
        return isinstance(self.gateway_sn, str) and self.gateway_sn.startswith("__")

    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            console.print("[yellow]MQTT 连接已断开[/yellow]")

    def get_connection_diagnostics(self) -> dict[str, Any]:
        return get_connection_diagnostics(self)

    def get_last_battery_msg_monotonic(self) -> Optional[float]:
        with self.lock:
            return self._last_battery_msg_monotonic

    def get_last_osd_msg_monotonic(self) -> Optional[float]:
        with self.lock:
            return self._last_osd_msg_monotonic

    def get_osd_message_count(self) -> int:
        with self.lock:
            return int(self._osd_message_count)

    def get_osd_timing_diagnostics(self, window_sec: float = 10.0) -> dict[str, Any]:
        return get_osd_timing_diagnostics(self, window_sec)

    def get_last_hsi_msg_monotonic(self) -> Optional[float]:
        with self.lock:
            return self._last_hsi_msg_monotonic

    def cleanup_request(self, tid: str):
        with self.lock:
            self.pending_requests.pop(tid, None)

    def get_latitude(self) -> Optional[float]:
        with self.lock:
            return self.osd_data["latitude"]

    def get_longitude(self) -> Optional[float]:
        with self.lock:
            return self.osd_data["longitude"]

    def get_height(self) -> Optional[float]:
        with self.lock:
            return self.osd_data["height"]

    def get_relative_height(self) -> Optional[float]:
        with self.lock:
            if self.osd_data["height"] is not None and self.takeoff_height is not None:
                return self.osd_data["height"] - self.takeoff_height
            return None

    def get_attitude_head(self) -> Optional[float]:
        with self.lock:
            return self.osd_data["attitude_head"]

    def get_speed(
        self,
    ) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        with self.lock:
            return (
                self.osd_data["horizontal_speed"],
                self.osd_data["speed_x"],
                self.osd_data["speed_y"],
                self.osd_data["speed_z"],
            )

    def get_battery_percent(self) -> Optional[int]:
        with self.lock:
            return self.osd_data["battery_percent"]

    def get_local_height(self) -> Optional[float]:
        with self.lock:
            return self.osd_data["down_distance"]

    def is_local_height_ok(self) -> bool:
        with self.lock:
            return self.osd_data["down_enable"] is True and self.osd_data["down_work"] is True

    def get_hsi_data(self) -> dict[str, Any]:
        return get_hsi_data(self)

    def get_around_distances(self) -> list[int]:
        return get_around_distances(self)

    def get_position(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        with self.lock:
            return (self.osd_data["latitude"], self.osd_data["longitude"], self.osd_data["height"])

    def get_flight_mode(self) -> Optional[int]:
        with self.lock:
            return self.drone_state["mode_code"]

    def get_flight_mode_name(self) -> str:
        with self.lock:
            mode_code = self.drone_state["mode_code"]
            if mode_code is None:
                return "未知"
            return MODE_NAMES.get(mode_code, f"未知模式({mode_code})")

    def get_drone_state(self) -> dict[str, Any]:
        with self.lock:
            return self.drone_state.copy()

    def get_aircraft_sn(self) -> Optional[str]:
        return get_aircraft_sn(self)

    def get_topo_data(self) -> Optional[dict[str, Any]]:
        with self.lock:
            return self.topo_data.copy() if self.topo_data else None

    def get_payload_index(self) -> Optional[str]:
        with self.lock:
            return self.camera_osd["payload_index"]

    def get_gimbal_attitude(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        with self.lock:
            return (
                self.camera_osd["gimbal_pitch"],
                self.camera_osd["gimbal_roll"],
                self.camera_osd["gimbal_yaw"],
            )

    def wait_for_gimbal_attitude(
        self, timeout: float = 10.0, poll_interval: float = 0.2
    ) -> tuple[float, float, float]:
        return wait_for_gimbal_attitude(self, timeout, poll_interval)

    def get_camera_osd_data(self) -> dict[str, Any]:
        with self.lock:
            return self.camera_osd.copy()

    def get_flyto_progress(self) -> dict[str, Any]:
        with self.lock:
            return self.flyto_progress.copy()

    def get_flyto_status(self) -> Optional[str]:
        with self.lock:
            return self.flyto_progress["status"]

    def wait_for_flyto_event(
        self, expected_fly_to_id: str, timeout: float = 120.0, poll_interval: float = 1.0
    ) -> dict[str, Any]:
        return wait_for_flyto_event(self, expected_fly_to_id, timeout, poll_interval)

    def register_osd_callback(self, callback):
        self.osd_callbacks.append(callback)

    def get_osd_frequency(self) -> float:
        return get_osd_frequency(self)

    def is_online(self, timeout: float = 2.0) -> bool:
        return is_online(self, timeout)

    def publish(self, method: str, data: dict[str, Any], tid: str):
        return publish_service(self, method, data, tid, console)

    def _on_message(self, client, userdata, msg):
        try:
            handle_message(self, msg, console)
        except Exception as exc:
            console.print(f"[red]消息处理异常: {exc}[/red]")

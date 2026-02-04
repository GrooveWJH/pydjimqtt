"""
DRC 连接管理器 - 自动重连机制

功能：
1. 监控 DRC 连接健康状态
2. 检测到离线时自动重连（重试10次，每次等待1秒）
3. 提供连接状态查询接口（供 UI 显示）

设计原则：
- 简单直接，不使用复杂设计模式
- 使用后台线程监控连接状态
- 状态机模型：online → reconnecting → online/offline
"""

import time
import threading
from typing import Dict, Any, Optional, Callable
from rich.console import Console

from ..core import MQTTClient, ServiceCaller
from .commands import enter_drc_mode, request_control_auth
from .heartbeat import start_heartbeat, stop_heartbeat

console = Console()


class ConnectionState:
    """连接状态枚举"""

    ONLINE = "online"  # 在线
    RECONNECTING = "reconnecting"  # 重连中
    OFFLINE = "offline"  # 离线


class DRCConnectionManager:
    """
    DRC 连接管理器

    职责：
    1. 监控 MQTT OSD 消息频率
    2. 检测到离线时触发重连
    3. 重连失败 10 次后标记为离线

    线程安全：所有状态访问都通过锁保护
    """

    def __init__(
        self,
        mqtt_client: MQTTClient,
        service_caller: ServiceCaller,
        uav_config: Dict[str, Any],
        mqtt_config: Dict[str, Any],
        osd_frequency: int = 100,
        hsi_frequency: int = 10,
        offline_timeout: float = 2.0,
        reconnect_attempts: int = 10,
        reconnect_interval: float = 1.0,
    ):
        """
        初始化连接管理器

        Args:
            mqtt_client: MQTT 客户端
            service_caller: 服务调用器
            uav_config: 无人机配置（sn, user_id, callsign）
            mqtt_config: MQTT 配置（host, port, username, password）
            osd_frequency: OSD 数据频率（Hz）
            hsi_frequency: HSI 数据频率（Hz）
            offline_timeout: 离线检测超时时间（秒）
            reconnect_attempts: 最大重连次数
            reconnect_interval: 重连间隔（秒）
        """
        self.mqtt = mqtt_client
        self.caller = service_caller
        self.uav_config = uav_config
        self.mqtt_config = mqtt_config
        self.osd_frequency = osd_frequency
        self.hsi_frequency = hsi_frequency
        self.offline_timeout = offline_timeout
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_interval = reconnect_interval

        # 连接状态
        self.state = ConnectionState.ONLINE
        self.state_lock = threading.Lock()

        # 心跳线程
        self.heartbeat_thread = None

        # 监控线程
        self.monitor_thread = None
        self.stop_flag = threading.Event()

        # 回调函数（供 UI 订阅状态变化）
        self.on_state_change: Optional[Callable[[str], None]] = None

    def get_state(self) -> str:
        """
        获取当前连接状态（线程安全）

        Returns:
            'online', 'reconnecting', 'offline'
        """
        with self.state_lock:
            return self.state

    def is_online(self) -> bool:
        """判断是否在线"""
        return self.get_state() == ConnectionState.ONLINE

    def is_reconnecting(self) -> bool:
        """判断是否正在重连"""
        return self.get_state() == ConnectionState.RECONNECTING

    def get_heartbeat_thread(self):
        """
        获取当前心跳线程引用（线程安全）

        Returns:
            当前心跳线程对象，如果没有则返回 None
        """
        return self.heartbeat_thread

    def _set_state(self, new_state: str):
        """
        设置连接状态并触发回调（线程安全）

        Args:
            new_state: 新状态
        """
        with self.state_lock:
            if self.state != new_state:
                old_state = self.state
                self.state = new_state
                callsign = self.uav_config.get("callsign", "UAV")
                console.print(
                    f"[bright_yellow][{callsign}] 状态变化: {old_state} → {new_state}[/bright_yellow]"
                )

                # 触发回调（在锁外执行，避免死锁）
                if self.on_state_change:
                    # 在新线程中执行回调，避免阻塞监控线程
                    threading.Thread(
                        target=self.on_state_change, args=(new_state,), daemon=True
                    ).start()

    def _reconnect_drc(self) -> bool:
        """
        重新进入 DRC 模式

        Returns:
            是否成功重连
        """
        callsign = self.uav_config.get("callsign", "UAV")

        try:
            # 1. 请求控制权
            console.print(f"[bright_cyan][{callsign}] 请求控制权...[/bright_cyan]")
            request_control_auth(
                self.caller,
                user_id=self.uav_config.get("user_id", "pilot"),
                user_callsign=callsign,
            )

            # 2. 进入 DRC 模式
            console.print(f"[bright_cyan][{callsign}] 进入 DRC 模式...[/bright_cyan]")
            import uuid

            random_suffix = str(uuid.uuid4())[:3]
            mqtt_broker_config = {
                "address": f"{self.mqtt_config['host']}:{self.mqtt_config['port']}",
                "client_id": f"drc-{self.uav_config['sn']}-{random_suffix}",
                "username": self.mqtt_config["username"],
                "password": self.mqtt_config["password"],
                "expire_time": int(time.time()) + 3600,
                "enable_tls": self.mqtt_config.get("enable_tls", False),
            }
            enter_drc_mode(
                self.caller,
                mqtt_broker=mqtt_broker_config,
                osd_frequency=self.osd_frequency,
                hsi_frequency=self.hsi_frequency,
            )

            # 3. 重启心跳
            if self.heartbeat_thread:
                stop_heartbeat(self.heartbeat_thread)

            self.heartbeat_thread = start_heartbeat(self.mqtt, interval=0.2)

            console.print(f"[bright_green]✓ [{callsign}] DRC 重连成功[/bright_green]")
            return True

        except Exception as e:
            console.print(f"[bright_red]✗ [{callsign}] DRC 重连失败: {e}[/bright_red]")
            return False

    def _monitor_loop(self):
        """
        监控循环（在后台线程中运行）

        策略：
        1. 每 0.5 秒检查一次 OSD 消息时间戳
        2. 如果超过 offline_timeout 秒未收到消息，触发重连
        3. 重连最多尝试 reconnect_attempts 次
        4. 重连成功后恢复 online 状态
        """
        callsign = self.uav_config.get("callsign", "UAV")

        while not self.stop_flag.is_set():
            time.sleep(0.5)  # 每 0.5 秒检查一次

            # 检查是否在线
            if not self.mqtt.is_online(timeout=self.offline_timeout):
                # 检测到离线
                current_state = self.get_state()

                if current_state == ConnectionState.ONLINE:
                    # 第一次检测到离线，开始重连
                    console.print(
                        f"[bright_yellow]⚠ [{callsign}] 检测到离线（{self.offline_timeout}秒无数据）[/bright_yellow]"
                    )
                    self._set_state(ConnectionState.RECONNECTING)

                    # 尝试重连
                    for attempt in range(1, self.reconnect_attempts + 1):
                        if self.stop_flag.is_set():
                            break

                        console.print(
                            f"[bright_cyan][{callsign}] 重连尝试 {attempt}/{self.reconnect_attempts}...[/bright_cyan]"
                        )

                        if self._reconnect_drc():
                            # 重连成功
                            self._set_state(ConnectionState.ONLINE)
                            break

                        # 等待后重试
                        if attempt < self.reconnect_attempts:
                            time.sleep(self.reconnect_interval)
                    else:
                        # 所有重连尝试均失败
                        console.print(
                            f"[bright_red]✗ [{callsign}] 重连失败（{self.reconnect_attempts}次尝试）[/bright_red]"
                        )
                        self._set_state(ConnectionState.OFFLINE)

            else:
                # 在线状态
                current_state = self.get_state()
                if current_state == ConnectionState.RECONNECTING:
                    # 从重连状态恢复到在线
                    self._set_state(ConnectionState.ONLINE)

    def start(self, heartbeat_thread: Optional[threading.Thread] = None):
        """
        启动连接管理器

        Args:
            heartbeat_thread: 外部传入的心跳线程（如果已启动）
        """
        self.heartbeat_thread = heartbeat_thread

        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

        callsign = self.uav_config.get("callsign", "UAV")
        console.print(f"[bright_green]✓ [{callsign}] 连接管理器已启动[/bright_green]")

    def stop(self):
        """停止连接管理器"""
        self.stop_flag.set()

        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)

        if self.heartbeat_thread:
            stop_heartbeat(self.heartbeat_thread)

        callsign = self.uav_config.get("callsign", "UAV")
        console.print(f"[bright_yellow][{callsign}] 连接管理器已停止[/bright_yellow]")

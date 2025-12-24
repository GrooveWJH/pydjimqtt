"""
无人机数据模拟器

在没有真实无人机时生成伪造数据，用于GUI调试。
所有数据基于时间戳和数学函数动态计算，无需后台线程。
"""
import time
import math
import threading
from typing import Optional, Tuple, Dict, Any


class MockMQTTClient:
    """
    模拟的MQTT客户端 - 接口与真实MQTTClient完全一致

    数据生成策略：
    - GPS位置：圆形飞行轨迹，半径50米，周期约60秒
    - 速度：与位置轨迹的导数一致（数学准确）
    - 电池：每分钟下降1%，最低20%
    - 航向角：跟随飞行方向（0-360度）
    """

    def __init__(self, gateway_sn: str, mqtt_config: Dict[str, Any], index: int = 0):
        """
        初始化模拟客户端

        Args:
            gateway_sn: 网关序列号
            mqtt_config: MQTT配置（Mock不使用，保持接口一致）
            index: 无人机索引（用于生成不同轨迹）
        """
        self.gateway_sn = gateway_sn
        self.config = mqtt_config
        self.client = self  # 兼容 client.publish() 调用
        self._connected = False

        # 启动时间戳
        self.start_time = time.time()

        # 每架无人机的相位偏移（用于生成不同轨迹）
        # 5架无人机均匀分布在圆周上（0°, 72°, 144°, 216°, 288°）
        self.phase_offset = index * (2 * math.pi / 5)

        # 起飞点坐标（深圳大学城附近）
        # 每架无人机间隔约100米
        self.base_lat = 22.5380 + index * 0.001
        self.base_lon = 113.9380 + index * 0.001
        self.base_height = 50.0  # 海拔基准（米）

        # 飞行参数
        self.flight_radius = 0.0005  # 飞行半径（约50米，纬度单位）
        self.angular_velocity = 0.1  # 角速度（弧度/秒，周期约60秒）
        self.vertical_amplitude = 5.0  # 垂直振荡幅度（米）
        self.vertical_frequency = 0.05  # 垂直振荡频率（弧度/秒）

        # 起飞点高度（用于计算相对高度）
        self.takeoff_height = self.base_height

    def connect(self):
        """模拟连接MQTT"""
        self._connected = True

    def disconnect(self):
        """模拟断开连接"""
        self._connected = False

    def _elapsed(self) -> float:
        """获取运行时长（秒）"""
        return time.time() - self.start_time

    # ========== GPS位置数据 ==========

    def get_position(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        获取当前位置（纬度, 经度, 高度）

        圆形飞行轨迹：
        - 水平面：以起飞点为圆心，半径50米
        - 垂直面：正弦波上下浮动，幅度5米

        Returns:
            (latitude, longitude, height)
        """
        t = self._elapsed()
        angle = self.angular_velocity * t + self.phase_offset

        # 水平位置（圆形轨迹）
        lat = self.base_lat + self.flight_radius * math.sin(angle)
        lon = self.base_lon + self.flight_radius * math.cos(angle)

        # 垂直位置（正弦波浮动）
        height = self.base_height + 20.0 + self.vertical_amplitude * math.sin(self.vertical_frequency * t)

        return (lat, lon, height)

    def get_latitude(self) -> Optional[float]:
        """获取纬度"""
        lat, _, _ = self.get_position()
        return lat

    def get_longitude(self) -> Optional[float]:
        """获取经度"""
        _, lon, _ = self.get_position()
        return lon

    def get_height(self) -> Optional[float]:
        """获取全局高度（GPS高度）"""
        _, _, height = self.get_position()
        return height

    def get_relative_height(self) -> Optional[float]:
        """
        获取距起飞点高度

        Returns:
            当前高度 - 起飞点高度
        """
        _, _, height = self.get_position()
        if height is not None and self.takeoff_height is not None:
            return height - self.takeoff_height
        return None

    # ========== 速度数据 ==========

    def get_speed(self) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """
        获取速度数据（水平速度, X轴速度, Y轴速度, Z轴速度）

        速度是位置的时间导数：
        - 位置: r * sin(wt) → 速度: r * w * cos(wt)
        - 纬度1度 ≈ 111km = 111000m

        Returns:
            (horizontal_speed, speed_x, speed_y, speed_z) 单位：m/s
        """
        t = self._elapsed()
        angle = self.angular_velocity * t + self.phase_offset

        # 切向速度大小（m/s）
        # v = r * w，其中r需要转换为米
        tangential_velocity = self.flight_radius * self.angular_velocity * 111000

        # 速度分量（数学准确的导数）
        speed_x = tangential_velocity * math.cos(angle)  # 纬度方向
        speed_y = -tangential_velocity * math.sin(angle)  # 经度方向（负号因为cos的导数）

        # 垂直速度（高度的导数）
        speed_z = self.vertical_amplitude * self.vertical_frequency * math.cos(self.vertical_frequency * t)

        # 水平速度（合成）
        horizontal_speed = math.sqrt(speed_x**2 + speed_y**2)

        return (horizontal_speed, speed_x, speed_y, speed_z)

    # ========== 姿态数据 ==========

    def get_attitude_head(self) -> Optional[float]:
        """
        获取航向角（度）

        航向角跟随圆形飞行方向：
        - 0°：正北
        - 90°：正东
        - 180°：正南
        - 270°：正西

        Returns:
            航向角 [0, 360)
        """
        t = self._elapsed()
        angle = self.angular_velocity * t + self.phase_offset

        # 转换为度数并归一化到 [0, 360)
        heading = math.degrees(angle) % 360
        return heading

    # ========== HSI数据（高度传感器）==========

    def get_local_height(self) -> Optional[float]:
        """
        获取HSI测高数据（厘米）

        HSI（Height Sensor Interface）是下视测距传感器。
        在模拟中，返回与相对高度一致的数据（单位：厘米）

        Returns:
            高度（厘米）
        """
        rel_height = self.get_relative_height()
        if rel_height is not None:
            return rel_height * 100  # 米转厘米
        return None

    def is_local_height_ok(self) -> bool:
        """
        判断HSI高度传感器是否正常工作

        模拟中始终返回True（传感器正常）
        """
        return True

    # ========== 电池数据 ==========

    def get_battery_percent(self) -> Optional[int]:
        """
        获取电池电量百分比

        模拟策略：
        - 每分钟下降1%
        - 最低20%（安全着陆电量）

        Returns:
            电量百分比 [20, 100]
        """
        elapsed_minutes = self._elapsed() / 60.0
        battery = 100 - int(elapsed_minutes)
        return max(20, battery)

    # ========== 飞行状态数据 ==========

    def get_flight_mode(self) -> Optional[int]:
        """
        获取飞行模式代码

        模拟策略：根据运行时间循环不同模式
        """
        t = self._elapsed()
        # 每30秒切换一次模式
        modes = [0, 3, 16, 9, 3, 0]  # 待机 → 手动 → 虚拟摇杆 → 返航 → 手动 → 待机
        index = int(t / 30) % len(modes)
        return modes[index]

    def get_flight_mode_name(self) -> str:
        """获取飞行模式名称（中文）"""
        mode_names = {
            0: "待机", 1: "起飞准备", 2: "起飞准备完毕", 3: "摇杆控制",
            4: "自动起飞", 5: "航线飞行", 6: "全景拍照", 7: "智能跟随",
            8: "ADS-B 躲避", 9: "自动返航", 10: "自动降落", 11: "强制降落",
            12: "三桨叶降落", 13: "升级中", 14: "未连接", 15: "APAS",
            16: "虚拟摇杆状态", 17: "指令飞行"
        }
        mode_code = self.get_flight_mode()
        if mode_code is None:
            return "未知"
        return mode_names.get(mode_code, f"未知模式({mode_code})")

    def get_drone_state(self) -> Dict[str, Any]:
        """
        获取完整的无人机状态数据

        返回模拟的状态信息
        """
        return {
            'mode_code': self.get_flight_mode(),
            'rth_altitude': 100,  # 返航高度100米
            'distance_limit': 5000,  # 距离限制5000米
            'height_limit': 420,  # 高度限制420米
            'is_in_fixed_speed': False,
            'night_lights_state': 0,
        }

    def get_aircraft_sn(self) -> Optional[str]:
        """获取无人机序列号（模拟）"""
        # 模拟：从网关 SN 生成一个对应的飞机 SN
        return f"AIRCRAFT_{self.gateway_sn[-6:]}"

    def get_topo_data(self) -> Optional[Dict[str, Any]]:
        """获取完整的拓扑数据（模拟）"""
        return {
            'domain': '2',
            'type': 174,
            'sub_type': 0,
            'device_secret': 'mock_secret',
            'nonce': 'mock_nonce',
            'thing_version': '1.2.0',
            'sub_devices': [
                {
                    'sn': f"AIRCRAFT_{self.gateway_sn[-6:]}",
                    'domain': '0',
                    'type': 99,
                    'sub_type': 0,
                    'index': 'A',
                    'device_secret': 'mock_aircraft_secret',
                    'nonce': 'mock_aircraft_nonce',
                    'thing_version': '1.2.0'
                }
            ]
        }

    def get_payload_index(self) -> Optional[str]:
        """获取相机负载索引（模拟，返回默认值 "88-0-0"）"""
        return "88-0-0"

    def get_gimbal_attitude(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """
        获取云台姿态 (pitch, roll, yaw)（模拟）

        模拟云台随时间缓慢变化
        """
        t = self._elapsed()
        pitch = 10.0 * math.sin(0.1 * t)  # -10° 到 +10° 摇头
        roll = 0.0  # 横滚始终为0
        yaw = 45.0 * math.sin(0.05 * t)  # -45° 到 +45° 左右转
        return (pitch, roll, yaw)

    def get_camera_osd_data(self) -> Dict[str, Any]:
        """获取完整的相机 OSD 数据（模拟）"""
        pitch, roll, yaw = self.get_gimbal_attitude()
        return {
            'payload_index': self.get_payload_index(),
            'gimbal_pitch': pitch,
            'gimbal_roll': roll,
            'gimbal_yaw': yaw,
        }

    # ========== 兼容方法（用于控制命令）==========

    def publish(self, topic: str, payload: str, qos: int = 0):
        """
        模拟发布MQTT消息

        Mock不实际发送消息，只打印日志
        """
        # 静默忽略（避免污染输出）
        pass

    def cleanup_request(self, tid: str):
        """兼容超时清理接口"""
        pass

    # ========== 新增：频率追踪和在线状态（与真实 MQTTClient 保持一致）==========

    def get_osd_frequency(self) -> float:
        """
        获取实时 OSD 消息频率（模拟）

        模拟中返回固定频率（100 Hz），因为模拟器是按需生成数据。

        Returns:
            频率（Hz）
        """
        return 100.0  # 模拟器固定返回 100 Hz

    def is_online(self, timeout: float = 2.0) -> bool:
        """
        检查无人机是否在线（模拟）

        模拟中始终返回 True（在线状态）。

        Args:
            timeout: 超时时间（秒），模拟中不使用

        Returns:
            True（始终在线）
        """
        return True  # 模拟器始终在线


class MockServiceCaller:
    """
    模拟的服务调用器

    GUI不调用服务（只读数据），此类仅占位以保持接口一致。
    """

    def __init__(self, mqtt_client: MockMQTTClient):
        self.mqtt = mqtt_client

    def call(self, method: str, data: Dict[str, Any] = None, timeout: int = 10) -> Dict[str, Any]:
        """
        模拟服务调用（总是返回成功）

        Returns:
            {'result': 0, 'data': {}, 'message': 'Mock success'}
        """
        return {
            'result': 0,
            'data': {},
            'message': 'Mock success'
        }


class MockHeartbeatThread(threading.Thread):
    """
    模拟的心跳线程

    特点：
    - 继承threading.Thread（兼容is_alive()检查）
    - 添加stop_flag属性（兼容stop_heartbeat()）
    - 不实际运行后台循环（节省资源）
    """

    def __init__(self):
        super().__init__(daemon=True)
        self.stop_flag = threading.Event()
        self._mock_alive = True
        self._started = False  # 标记是否已启动

    def is_alive(self) -> bool:
        """始终返回True（心跳正常）"""
        return self._mock_alive and not self.stop_flag.is_set()

    def run(self):
        """空运行（不需要实际后台任务）"""
        pass

    def start(self):
        """覆盖start方法，避免实际启动线程（但标记为已启动状态）"""
        self._started = True
        # 不调用 super().start()，避免启动真实线程

    def join(self, timeout=None):
        """覆盖join方法，立即返回（因为没有真实线程在运行）"""
        pass


# ========== 工厂函数 ==========

def create_mock_connections(uav_configs: list) -> list:
    """
    创建多个模拟连接

    接口与 setup_multiple_drc_connections() 完全一致

    Args:
        uav_configs: 无人机配置列表，每项包含：
            - 'sn': 序列号（必需）
            - 其他字段（Mock忽略）

    Returns:
        List[Tuple[MockMQTTClient, MockServiceCaller, MockHeartbeatThread]]
    """
    connections = []

    for index, config in enumerate(uav_configs):
        sn = config['sn']

        # 创建Mock对象
        mqtt = MockMQTTClient(sn, mqtt_config={}, index=index)
        mqtt.connect()

        caller = MockServiceCaller(mqtt)
        heartbeat = MockHeartbeatThread()

        connections.append((mqtt, caller, heartbeat))

    return connections

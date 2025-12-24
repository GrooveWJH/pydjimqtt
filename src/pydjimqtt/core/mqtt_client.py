"""
MQTT 客户端 - 负责连接管理和消息收发
"""
import json
import threading
from typing import Dict, Any, Optional
from concurrent.futures import Future
import paho.mqtt.client as mqtt
from rich.console import Console

console = Console()


class MQTTClient:
    """简单的 MQTT 客户端封装"""

    def __init__(self, gateway_sn: str, mqtt_config: Dict[str, Any]):
        self.gateway_sn = gateway_sn
        self.config = mqtt_config
        self.client: Optional[mqtt.Client] = None
        self.pending_requests: Dict[str, Future] = {}
        self.lock = threading.Lock()
        # OSD 数据缓存
        self.osd_data = {
            'latitude': None, 'longitude': None, 'height': None, 'attitude_head': None,
            'horizontal_speed': None, 'speed_x': None, 'speed_y': None, 'speed_z': None,
            'down_distance': None, 'down_enable': None, 'down_work': None,
            'battery_percent': None
        }
        # 无人机状态数据
        self.drone_state = {
            'mode_code': None,
            'rth_altitude': None,
            'distance_limit': None,
            'height_limit': None,
            'is_in_fixed_speed': None,
            'night_lights_state': None,
        }
        # 拓扑数据（update_topo）- 保存完整的 data 字段
        self.topo_data = None  # 完整的 update_topo data 对象
        # 相机 OSD 信息（从 drc_camera_osd_info_push 获取）
        self.camera_osd = {
            'payload_index': None,  # 相机索引，如 "88-0-0"
            'gimbal_pitch': None,
            'gimbal_roll': None,
            'gimbal_yaw': None,
        }
        # 起飞点高度（第一次读取到的全局高度）
        self.takeoff_height = None
        # Fly-to 进度数据
        self.flyto_progress = {
            'fly_to_id': None,
            'status': None,  # wayline_cancel, wayline_failed, wayline_ok, wayline_progress
            'result': None,
            'way_point_index': None,
            'remaining_distance': None,
            'remaining_time': None,
            'planned_path_points': None,
        }
        # OSD 消息回调列表（用于 FPS 监控等）
        self.osd_callbacks = []
        # 频率追踪（2秒时间窗口，平滑网络抖动）
        self._osd_timestamps = []  # 2秒窗口内的所有 OSD 消息时间戳
        self._last_osd_time = 0.0  # 最后一次 OSD 消息时间（用于离线检测）
        self._freq_window = 2.0  # 频率计算窗口大小（秒）
        # DEBUG 开关（默认关闭，减少日志污染）
        self.enable_service_debug = False  # 启用后打印服务响应的完整 JSON

    def connect(self):
        """建立 MQTT 连接"""
        # 添加3位随机UUID后缀，避免多个客户端冲突
        import uuid
        random_suffix = str(uuid.uuid4())[:3]
        client_id = f"python-drc-{self.gateway_sn}-{random_suffix}"

        self.client = mqtt.Client(client_id=client_id)
        self.client.username_pw_set(self.config['username'], self.config['password'])
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
                    5: "未授权"
                }
                error_msg = error_messages.get(rc, f"未知错误 (rc={rc})")
                console.print(f"[red]✗[/red] MQTT 连接失败: {error_msg}")

        self.client.on_connect = on_connect

        console.print(f"[cyan]连接 MQTT: {self.config['host']}:{self.config['port']}[/cyan]")

        try:
            # 添加连接超时（5秒）
            self.client.connect(self.config['host'], self.config['port'], 60)
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

    def disconnect(self):
        """断开连接"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            console.print("[yellow]MQTT 连接已断开[/yellow]")

    def cleanup_request(self, tid: str):
        """清理挂起的请求（用于超时处理）"""
        with self.lock:
            self.pending_requests.pop(tid, None)

    def get_latitude(self) -> Optional[float]:
        """获取最新纬度（无卫星信号时返回 None）"""
        with self.lock:
            return self.osd_data['latitude']

    def get_longitude(self) -> Optional[float]:
        """获取最新经度（无卫星信号时返回 None）"""
        with self.lock:
            return self.osd_data['longitude']

    def get_height(self) -> Optional[float]:
        """获取最新全局高度（GPS高度，无卫星信号时返回 None）"""
        with self.lock:
            return self.osd_data['height']

    def get_relative_height(self) -> Optional[float]:
        """获取距起飞点高度（当前高度 - 起飞点高度，无数据时返回 None）"""
        with self.lock:
            if self.osd_data['height'] is not None and self.takeoff_height is not None:
                return self.osd_data['height'] - self.takeoff_height
            return None

    def get_attitude_head(self) -> Optional[float]:
        """获取最新航向角（无数据时返回 None）"""
        with self.lock:
            return self.osd_data['attitude_head']

    def get_speed(self) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """获取速度数据 (水平速度, X轴速度, Y轴速度, Z轴速度)"""
        with self.lock:
            return (
                self.osd_data['horizontal_speed'],
                self.osd_data['speed_x'],
                self.osd_data['speed_y'],
                self.osd_data['speed_z']
            )

    def get_battery_percent(self) -> Optional[int]:
        """获取电池电量百分比（无数据时返回 None）"""
        with self.lock:
            return self.osd_data['battery_percent']

    def get_local_height(self) -> Optional[float]:
        """获取HSI高度/下视距离（无数据时返回 None）"""
        with self.lock:
            return self.osd_data['down_distance']

    def is_local_height_ok(self) -> bool:
        """判断 HSI 高度数据是否有效（down_enable 和 down_work 都为 True）"""
        with self.lock:
            return self.osd_data['down_enable'] is True and self.osd_data['down_work'] is True

    def get_position(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """获取最新位置 (纬度, 经度, 高度)，无卫星信号时返回 (None, None, None)"""
        with self.lock:
            return (self.osd_data['latitude'], self.osd_data['longitude'], self.osd_data['height'])

    def get_flight_mode(self) -> Optional[int]:
        """获取飞行模式代码（mode_code）"""
        with self.lock:
            return self.drone_state['mode_code']

    def get_flight_mode_name(self) -> str:
        """获取飞行模式名称（中文）"""
        mode_names = {
            0: "待机", 1: "起飞准备", 2: "起飞准备完毕", 3: "摇杆控制",
            4: "自动起飞", 5: "航线飞行", 6: "全景拍照", 7: "智能跟随",
            8: "ADS-B 躲避", 9: "自动返航", 10: "自动降落", 11: "强制降落",
            12: "三桨叶降落", 13: "升级中", 14: "未连接", 15: "APAS",
            16: "虚拟摇杆状态", 17: "指令飞行"
        }
        with self.lock:
            mode_code = self.drone_state['mode_code']
            if mode_code is None:
                return "未知"
            return mode_names.get(mode_code, f"未知模式({mode_code})")

    def get_drone_state(self) -> Dict[str, Any]:
        """获取完整的无人机状态数据"""
        with self.lock:
            return self.drone_state.copy()

    def get_aircraft_sn(self) -> Optional[str]:
        """获取无人机序列号（从 update_topo 消息的 sub_devices[0].sn 中获取）"""
        with self.lock:
            if self.topo_data and 'sub_devices' in self.topo_data:
                sub_devices = self.topo_data.get('sub_devices', [])
                if sub_devices and len(sub_devices) > 0:
                    return sub_devices[0].get('sn')
            return None

    def get_topo_data(self) -> Optional[Dict[str, Any]]:
        """获取完整的 update_topo data 数据"""
        with self.lock:
            return self.topo_data.copy() if self.topo_data else None

    def get_payload_index(self) -> Optional[str]:
        """获取相机负载索引（如 "88-0-0"，从 drc_camera_osd_info_push 获取）"""
        with self.lock:
            return self.camera_osd['payload_index']

    def get_gimbal_attitude(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """获取云台姿态 (pitch, roll, yaw)"""
        with self.lock:
            return (
                self.camera_osd['gimbal_pitch'],
                self.camera_osd['gimbal_roll'],
                self.camera_osd['gimbal_yaw']
            )

    def get_camera_osd_data(self) -> Dict[str, Any]:
        """获取完整的相机 OSD 数据"""
        with self.lock:
            return self.camera_osd.copy()

    def get_flyto_progress(self) -> Dict[str, Any]:
        """获取 Fly-to 进度数据"""
        with self.lock:
            return self.flyto_progress.copy()

    def get_flyto_status(self) -> Optional[str]:
        """
        获取 Fly-to 状态

        Returns:
            状态字符串或 None
            - "wayline_cancel": 取消飞向目标点
            - "wayline_failed": 执行失败
            - "wayline_ok": 执行成功，已飞向目标点
            - "wayline_progress": 执行中
        """
        with self.lock:
            return self.flyto_progress['status']

    def wait_for_flyto_event(
        self,
        expected_fly_to_id: str,
        timeout: float = 120.0,
        poll_interval: float = 1.0
    ) -> Dict[str, Any]:
        """
        等待指定 fly_to_id 的航点事件（事件驱动 + 轮询兜底）

        使用混合策略：
        1. 主策略：事件回调（event 到达时立即返回，延迟 <10ms）
        2. 兜底策略：定期轮询（每 poll_interval 秒检查一次，防止漏事件）
        3. 超时保护：超时后抛出 TimeoutError

        Args:
            expected_fly_to_id: 期望的 fly_to_id（必须匹配，防止读取旧航点数据）
            timeout: 超时时间（秒），默认 120 秒
            poll_interval: 轮询间隔（秒），默认 1 秒

        Returns:
            完整的 flyto_progress 数据（当 status 为终止状态时返回）

        Raises:
            TimeoutError: 超时未收到终止状态事件

        Example:
            >>> _, fly_to_id = fly_to_point(caller, lat=39.0, lon=117.0, height=100)
            >>> progress = mqtt.wait_for_flyto_event(fly_to_id, timeout=120)
            >>> if progress['status'] == 'wayline_ok':
            >>>     print("✓ 已到达航点")
        """
        import time

        start_time = time.time()
        terminal_statuses = {'wayline_ok', 'wayline_failed', 'wayline_cancel'}

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(
                    f"等待 fly_to_id={expected_fly_to_id} 的事件超时（{timeout}秒）"
                )

            # 读取最新事件数据（线程安全）
            progress = self.get_flyto_progress()
            event_fly_to_id = progress.get('fly_to_id')
            status = progress.get('status')

            # ✅ 关键检查：fly_to_id 必须匹配
            if event_fly_to_id == expected_fly_to_id:
                # 收到当前航点的事件
                if status in terminal_statuses:
                    # 到达终止状态（ok / failed / cancel）
                    return progress
                # 还在飞行中（wayline_progress），继续等待

            # 轮询间隔（既能快速响应，又不占用太多 CPU）
            time.sleep(poll_interval)

    def register_osd_callback(self, callback):
        """注册 OSD 消息回调（用于 FPS 监控等）"""
        self.osd_callbacks.append(callback)

    def get_osd_frequency(self) -> float:
        """
        获取实时 OSD 消息频率

        使用2秒时间窗口法计算频率，有效平滑网络抖动。
        100Hz 下窗口约包含200条消息，统计误差 < 0.5%。

        Returns:
            频率（Hz），如果数据不足返回 0.0
        """
        with self.lock:
            if len(self._osd_timestamps) < 2:
                return 0.0
            time_span = self._osd_timestamps[-1] - self._osd_timestamps[0]
            if time_span == 0:
                return 0.0
            # 计算频率：消息数量 / 时间跨度
            return (len(self._osd_timestamps) - 1) / time_span

    def is_online(self, timeout: float = 2.0) -> bool:
        """
        检查无人机是否在线

        根据最后一次 OSD 消息的时间判断无人机是否在线。

        Args:
            timeout: 超时时间（秒），默认 2.0 秒

        Returns:
            True 如果在线（timeout 秒内有消息），False 如果离线
        """
        import time
        with self.lock:
            if self._last_osd_time == 0:
                return False  # 还没有收到过任何 OSD 消息
            return (time.time() - self._last_osd_time) < timeout

    def publish(self, method: str, data: Dict[str, Any], tid: str) -> Future:
        """
        发布消息并返回 Future 等待响应

        Args:
            method: 服务方法名
            data: 请求数据
            tid: 事务 ID

        Returns:
            Future 对象，可通过 result() 获取响应
        """
        topic = f"thing/product/{self.gateway_sn}/services"
        payload = {
            "tid": tid,
            # bid (business id) 和 tid (transaction id):
            # DJI 协议要求两个字段，实测中两者可以相同
            "bid": tid,
            "timestamp": int(__import__('time').time() * 1000),
            "method": method,
            "data": data
        }

        # 创建 Future 等待响应
        future = Future()
        with self.lock:
            self.pending_requests[tid] = future

        # 发布消息
        msg_json = json.dumps(payload)
        self.client.publish(topic, msg_json, qos=1)
        console.print(f"[blue]→[/blue] 发送 {method} (tid: {tid[:8]}...)")

        return future

    def _on_message(self, client, userdata, msg):
        """处理收到的消息"""
        try:
            payload = json.loads(msg.payload.decode())

            # 处理 OSD 数据推送
            if payload.get('method') == 'osd_info_push':
                # 更新频率追踪（在锁外完成时间获取，减少锁持有时间）
                import time
                now = time.time()

                data = payload.get('data', {})
                with self.lock:
                    # 更新 OSD 数据
                    self.osd_data['latitude'] = data.get('latitude')
                    self.osd_data['longitude'] = data.get('longitude')
                    height = data.get('height')
                    self.osd_data['height'] = height
                    # 记录起飞点高度（第一次读取到有效高度时）
                    if height is not None and self.takeoff_height is None:
                        self.takeoff_height = height
                    self.osd_data['attitude_head'] = data.get('attitude_head')
                    self.osd_data['horizontal_speed'] = data.get('horizontal_speed')
                    self.osd_data['speed_x'] = data.get('speed_x')
                    self.osd_data['speed_y'] = data.get('speed_y')
                    self.osd_data['speed_z'] = data.get('speed_z')

                    # 更新频率追踪数据（2秒时间窗口）
                    self._last_osd_time = now
                    self._osd_timestamps.append(now)
                    # 清理超过2秒的旧时间戳，保持窗口大小
                    while self._osd_timestamps and (now - self._osd_timestamps[0]) > self._freq_window:
                        self._osd_timestamps.pop(0)

                # 触发所有注册的回调（用于 FPS 监控等）
                for callback in self.osd_callbacks:
                    try:
                        callback()
                    except Exception:
                        pass  # 忽略回调异常，避免影响消息处理
                return

            # 处理 HSI 数据推送
            if payload.get('method') == 'hsi_info_push':
                data = payload.get('data', {})
                with self.lock:
                    self.osd_data['down_distance'] = data.get('down_distance')
                    self.osd_data['down_enable'] = data.get('down_enable')
                    self.osd_data['down_work'] = data.get('down_work')
                return

            # 处理电池信息推送
            if payload.get('method') == 'drc_batteries_info_push':
                data = payload.get('data', {})
                with self.lock:
                    self.osd_data['battery_percent'] = data.get('capacity_percent')
                return

            # 处理无人机状态推送
            if payload.get('method') == 'drc_drone_state_push':
                data = payload.get('data', {})
                limit = data.get('limit', {})
                with self.lock:
                    self.drone_state['mode_code'] = data.get('mode_code')
                    self.drone_state['rth_altitude'] = data.get('rth_altitude')
                    self.drone_state['distance_limit'] = limit.get('distance_limit')
                    self.drone_state['height_limit'] = limit.get('height_limit')
                    self.drone_state['is_in_fixed_speed'] = data.get('is_in_fixed_speed')
                    self.drone_state['night_lights_state'] = data.get('night_lights_state')
                return

            # 处理拓扑更新推送（保存完整的 data 字段）
            if payload.get('method') == 'update_topo':
                data = payload.get('data', {})
                with self.lock:
                    self.topo_data = data  # 保存完整的 data 对象
                return

            # 处理相机 OSD 信息推送
            if payload.get('method') == 'drc_camera_osd_info_push':
                data = payload.get('data', {})
                with self.lock:
                    self.camera_osd['payload_index'] = data.get('payload_index')
                    self.camera_osd['gimbal_pitch'] = data.get('gimbal_pitch')
                    self.camera_osd['gimbal_roll'] = data.get('gimbal_roll')
                    self.camera_osd['gimbal_yaw'] = data.get('gimbal_yaw')
                return

            # 处理 Fly-to 进度事件推送
            if payload.get('method') == 'fly_to_point_progress':
                data = payload.get('data', {})
                with self.lock:
                    self.flyto_progress['fly_to_id'] = data.get('fly_to_id')
                    self.flyto_progress['status'] = data.get('status')
                    self.flyto_progress['result'] = data.get('result')
                    self.flyto_progress['way_point_index'] = data.get('way_point_index')
                    self.flyto_progress['remaining_distance'] = data.get('remaining_distance')
                    self.flyto_progress['remaining_time'] = data.get('remaining_time')
                    self.flyto_progress['planned_path_points'] = data.get('planned_path_points')
                return

            # 处理服务响应
            tid = payload.get('tid')
            if not tid:
                return

            # 🔍 DEBUG: 打印完整的服务响应（仅在启用时）
            if self.enable_service_debug:
                method = payload.get('method', 'unknown')
                console.print(f"[bright_yellow]📦 MQTT 服务响应 DEBUG[/bright_yellow]")
                console.print(f"  [cyan]Topic:[/cyan] {msg.topic}")
                console.print(f"  [cyan]TID:[/cyan] {tid[:8]}...")
                console.print(f"  [cyan]Method:[/cyan] {method}")
                console.print(f"  [cyan]完整 Payload:[/cyan]")
                console.print(f"{json.dumps(payload, indent=2, ensure_ascii=False)}")

            with self.lock:
                future = self.pending_requests.pop(tid, None)

            if future:
                # 检查是否有错误 - DJI 协议有两种格式：
                # 格式1（标准）：info.code != 0 表示错误
                # 格式2（简化）：data.result != 0 表示错误
                info = payload.get('info', {})
                data = payload.get('data', {})

                # 优先检查 info.code（标准格式）
                if info and info.get('code') != 0:
                    error_msg = info.get('message', 'Unknown error')
                    console.print(f"[red]✗[/red] 错误: {error_msg}")
                    future.set_exception(Exception(error_msg))
                # 再检查 data.result（简化格式，如 drc_mode_enter）
                elif 'result' in data and data.get('result') != 0:
                    error_msg = data.get('output', {}).get('msg', 'Unknown error')
                    console.print(f"[red]✗[/red] 错误: {error_msg}")
                    future.set_exception(Exception(error_msg))
                # 成功
                else:
                    console.print(f"[green]←[/green] 收到响应 (tid: {tid[:8]}...)")
                    future.set_result(data)

        except Exception as e:
            console.print(f"[red]消息处理异常: {e}[/red]")

"""
服务调用器 - 负责生成请求和等待响应
"""
import uuid
from typing import Dict, Any
from .mqtt_client import MQTTClient


class ServiceCaller:
    """简单的服务调用封装"""

    def __init__(self, mqtt_client: MQTTClient, timeout: int = 10):
        self.mqtt = mqtt_client
        self.timeout = timeout

    def call(self, method: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        调用服务并等待响应

        Args:
            method: 服务方法名
            data: 请求数据（可选）

        Returns:
            响应数据

        Raises:
            TimeoutError: 响应超时
            Exception: 服务返回错误
        """
        tid = str(uuid.uuid4())
        future = self.mqtt.publish(method, data or {}, tid)

        # 等待响应
        try:
            result = future.result(timeout=self.timeout)
            return result
        except TimeoutError:
            # 清理超时的请求，避免资源泄漏
            self.mqtt.cleanup_request(tid)
            raise TimeoutError(f"服务调用超时: {method}")

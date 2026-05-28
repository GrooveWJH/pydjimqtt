from __future__ import annotations

from typing import Any


class MockServiceCaller:
    """模拟的服务调用器。"""

    def __init__(self, mqtt_client):
        self.mqtt = mqtt_client

    def call(
        self,
        method: str,
        data: dict[str, Any] | None = None,
        timeout: int = 10,
    ) -> dict[str, Any]:
        return {"result": 0, "data": {}, "message": "Mock success"}

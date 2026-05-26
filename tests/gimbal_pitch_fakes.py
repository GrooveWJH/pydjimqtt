from __future__ import annotations

import json
from typing import cast

from pydjimqtt import MQTTClient


class FakePahoClient:
    def __init__(self) -> None:
        self.published: list[dict] = []
        self.on_publish_callback = None

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self.published.append({"topic": topic, "payload": json.loads(payload), "qos": qos})
        if self.on_publish_callback is not None:
            self.on_publish_callback()


class FakeMQTTClient:
    def __init__(
        self,
        *,
        payload_index: str | None = "88-0-0",
        pitch_values: list[float | None] | None = None,
        stale_reads_after_publish: int = 0,
    ) -> None:
        self.gateway_sn = "9N9CN180011TJN"
        self.client: FakePahoClient | None = FakePahoClient()
        self.payload_index = payload_index
        self.pitch_values = pitch_values or [-60.0, -45.2, -45.1]
        self.pitch_reads = 0
        self.stale_reads_after_publish = stale_reads_after_publish
        self.pending_stale_reads = 0
        self.last_pitch: float | None = None
        if self.client is not None:
            self.client.on_publish_callback = self._on_publish

    def _on_publish(self) -> None:
        self.pending_stale_reads = self.stale_reads_after_publish

    def get_payload_index(self) -> str | None:
        return self.payload_index

    def get_gimbal_attitude(self) -> tuple[float | None, float | None, float | None]:
        if self.pending_stale_reads > 0:
            self.pending_stale_reads -= 1
            return self.last_pitch, 0.0, -90.0
        index = min(self.pitch_reads, len(self.pitch_values) - 1)
        self.pitch_reads += 1
        self.last_pitch = self.pitch_values[index]
        return self.last_pitch, 0.0, -90.0

    def wait_for_gimbal_attitude(
        self,
        timeout: float = 10.0,
        poll_interval: float = 0.2,
    ) -> tuple[float, float, float]:
        pitch, roll, yaw = self.get_gimbal_attitude()
        if pitch is None or roll is None or yaw is None:
            raise TimeoutError("gimbal attitude is not available")
        return float(pitch), float(roll), float(yaw)


def moving_payloads(mqtt: FakeMQTTClient) -> list[dict]:
    assert mqtt.client is not None
    return [
        item["payload"]
        for item in mqtt.client.published
        if item["payload"]["data"]["pitch_speed"] != 0
    ]


def as_mqtt_client(mqtt: FakeMQTTClient) -> MQTTClient:
    return cast(MQTTClient, mqtt)

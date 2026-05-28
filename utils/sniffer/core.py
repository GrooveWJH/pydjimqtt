"""Core MQTT topic sniffer."""

import json
import time
from collections import defaultdict
from typing import Any

from pydjimqtt import MQTTClient


class TopicSniffer:
    """Capture and classify messages across multiple MQTT topics."""

    def __init__(self, mqtt_client: MQTTClient, topics: list[str]):
        self.mqtt = mqtt_client
        self.topics = topics
        client = mqtt_client.client
        if client is None:
            raise RuntimeError("MQTT client is not connected")

        self.topic_stats: dict[str, dict[str, Any]] = {
            topic: {
                "message_counts": defaultdict(int),
                "latest_messages": {},
                "first_time": {},
                "last_time": {},
                "total_count": 0,
            }
            for topic in topics
        }
        self.start_time = time.time()
        self._original_on_message = client.on_message
        client.on_message = self._on_message_wrapper
        for topic in topics:
            client.subscribe(topic, qos=0)

    def _on_message_wrapper(self, client, userdata, msg) -> None:
        if self._original_on_message:
            self._original_on_message(client, userdata, msg)
        if msg.topic not in self.topics:
            return

        try:
            payload = json.loads(msg.payload.decode())
            method = payload.get("method", payload.get("event_name", "unknown"))
            stats = self.topic_stats[msg.topic]
            now = time.time()
            stats["message_counts"][method] += 1
            stats["latest_messages"][method] = payload
            stats["last_time"][method] = now
            stats["total_count"] += 1
            if method not in stats["first_time"]:
                stats["first_time"][method] = now
        except Exception:
            pass

    def get_frequency(self, topic: str, method: str) -> float:
        stats = self.topic_stats[topic]
        if method not in stats["first_time"] or method not in stats["last_time"]:
            return 0.0
        count = stats["message_counts"][method]
        if count <= 1:
            return 0.0
        time_span = stats["last_time"][method] - stats["first_time"][method]
        return (count - 1) / time_span if time_span > 0 else 0.0

    def render_status(self):
        from .rendering import render_status

        return render_status(self)

    def save_to_directory(self, base_dir: str):
        from .storage import save_to_directory

        return save_to_directory(self, base_dir)

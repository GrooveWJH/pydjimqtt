"""MQTT client for the HSI obstacle viewer."""

from __future__ import annotations

import json
import queue
from typing import Any

try:
    import paho.mqtt.client as mqtt
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"paho-mqtt not available: {exc}")

from .formatters import to_bool, to_int
from .models import HsiFrame


class HsiMqttClient:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        topic: str,
        username: str,
        password: str,
        out_queue: queue.Queue[HsiFrame],
    ) -> None:
        self.host = host
        self.port = port
        self.topic = topic
        self._queue = out_queue

        self._client = mqtt.Client()
        if username:
            self._client.username_pw_set(username, password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self.connected = False
        self.last_disconnect_rc: int | None = None

    def start(self) -> None:
        self._client.connect(self.host, self.port, keepalive=60)
        self._client.loop_start()

    def stop(self) -> None:
        try:
            self._client.loop_stop()
        finally:
            try:
                self._client.disconnect()
            except Exception:
                pass

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, rc: int) -> None:
        self.connected = rc == 0
        if rc == 0:
            client.subscribe(self.topic, qos=0)
            print(f"[MQTT] connected rc={rc}, subscribed: {self.topic}")
        else:
            print(f"[MQTT] connect failed rc={rc}")

    def _on_disconnect(self, _client: mqtt.Client, _userdata: Any, rc: int) -> None:
        self.connected = False
        self.last_disconnect_rc = rc
        print(f"[MQTT] disconnected rc={rc}")

    def _on_message(self, _client: mqtt.Client, _userdata: Any, msg: Any) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8", errors="ignore"))
        except Exception:
            return

        frame = _parse_hsi_frame(payload)
        if frame is not None:
            _put_latest(self._queue, frame)


def _parse_hsi_frame(payload: dict[str, Any]) -> HsiFrame | None:
    if str(payload.get("method") or "") != "hsi_info_push":
        return None

    data = payload.get("data")
    if not isinstance(data, dict):
        return None

    return HsiFrame(
        ts_ms=to_int(payload.get("timestamp")),
        seq=to_int(payload.get("seq")),
        around_distances_mm=_parse_around_distances(data),
        up_distance_mm=to_int(data.get("up_distance")),
        down_distance_mm=to_int(data.get("down_distance")),
        up_enable=to_bool(data.get("up_enable")),
        up_work=to_bool(data.get("up_work")),
        down_enable=to_bool(data.get("down_enable")),
        down_work=to_bool(data.get("down_work")),
        left_enable=to_bool(data.get("left_enable")),
        left_work=to_bool(data.get("left_work")),
        right_enable=to_bool(data.get("right_enable")),
        right_work=to_bool(data.get("right_work")),
        front_enable=to_bool(data.get("front_enable")),
        front_work=to_bool(data.get("front_work")),
        back_enable=to_bool(data.get("back_enable")),
        back_work=to_bool(data.get("back_work")),
        vertical_enable=to_bool(data.get("vertical_enable")),
        vertical_work=to_bool(data.get("vertical_work")),
        horizontal_enable=to_bool(data.get("horizontal_enable")),
        horizontal_work=to_bool(data.get("horizontal_work")),
    )


def _parse_around_distances(data: dict[str, Any]) -> list[int]:
    around = data.get("around_distances")
    if not isinstance(around, list):
        return []
    return [parsed for item in around if (parsed := to_int(item)) is not None]


def _put_latest(out_queue: queue.Queue[HsiFrame], frame: HsiFrame) -> None:
    try:
        out_queue.put_nowait(frame)
        return
    except queue.Full:
        pass

    try:
        _ = out_queue.get_nowait()
    except queue.Empty:
        pass
    try:
        out_queue.put_nowait(frame)
    except queue.Full:
        pass

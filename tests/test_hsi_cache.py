from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace

import pytest

from pydjimqtt.core.mqtt_client import MQTTClient


def _make_client() -> MQTTClient:
    return MQTTClient(
        "__test__",
        {"host": "127.0.0.1", "port": 1883, "username": "", "password": ""},
    )


def _push_message(client: MQTTClient, payload: dict) -> None:
    msg = SimpleNamespace(payload=json.dumps(payload).encode("utf-8"))
    client._on_message(None, None, msg)


def test_hsi_info_push_populates_cache_and_monotonic_timestamp() -> None:
    client = _make_client()
    _push_message(
        client,
        {
            "method": "hsi_info_push",
            "seq": 18,
            "timestamp": 1773379250075,
            "data": {
                "around_distances": [60000, 2400, 1900],
                "up_distance": 60000,
                "down_distance": 1234,
                "up_enable": True,
                "up_work": True,
                "down_enable": True,
                "down_work": True,
                "front_enable": True,
                "front_work": True,
            },
        },
    )

    snapshot = client.get_hsi_data()
    assert snapshot["seq"] == 18
    assert snapshot["timestamp"] == 1773379250075
    assert snapshot["around_distances"] == [60000, 2400, 1900]
    assert snapshot["down_distance"] == 1234
    assert client.get_around_distances() == [60000, 2400, 1900]
    assert client.get_last_hsi_msg_monotonic() is not None


def test_hsi_getters_return_copies() -> None:
    client = _make_client()
    _push_message(
        client,
        {
            "method": "hsi_info_push",
            "data": {"around_distances": [10, 20, 30]},
        },
    )

    hsi_snapshot = client.get_hsi_data()
    around_snapshot = client.get_around_distances()
    hsi_snapshot["around_distances"].append(99)
    around_snapshot.append(88)

    assert client.get_around_distances() == [10, 20, 30]


def test_hsi_empty_data_keeps_empty_array() -> None:
    client = _make_client()
    _push_message(
        client,
        {
            "method": "hsi_info_push",
            "data": {},
        },
    )

    assert client.get_around_distances() == []
    snapshot = client.get_hsi_data()
    assert snapshot["around_distances"] == []


def test_wait_for_gimbal_attitude_returns_after_camera_osd_arrives() -> None:
    client = _make_client()

    def delayed_camera_osd() -> None:
        time.sleep(0.02)
        _push_message(
            client,
            {
                "method": "drc_camera_osd_info_push",
                "data": {
                    "payload_index": "88-0-0",
                    "gimbal_pitch": -32.5,
                    "gimbal_roll": 1.25,
                    "gimbal_yaw": 92.0,
                },
            },
        )

    thread = threading.Thread(target=delayed_camera_osd)
    thread.start()
    try:
        assert client.wait_for_gimbal_attitude(timeout=1.0, poll_interval=0.01) == (
            -32.5,
            1.25,
            92.0,
        )
    finally:
        thread.join(timeout=1.0)


def test_wait_for_gimbal_attitude_times_out_without_camera_osd() -> None:
    client = _make_client()

    with pytest.raises(TimeoutError, match="gimbal attitude"):
        client.wait_for_gimbal_attitude(timeout=0.01, poll_interval=0.005)

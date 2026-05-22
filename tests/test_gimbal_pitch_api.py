from __future__ import annotations

import json
import threading
import time
from concurrent.futures import Future

import pytest


class _FakePahoClient:
    def __init__(self) -> None:
        self.published: list[dict] = []

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self.published.append(
            {"topic": topic, "payload": json.loads(payload), "qos": qos}
        )


class _FakeMQTTClient:
    def __init__(
        self,
        *,
        payload_index: str | None = "88-0-0",
        pitch_values: list[float | None] | None = None,
    ) -> None:
        self.gateway_sn = "9N9CN180011TJN"
        self.client = _FakePahoClient()
        self.payload_index = payload_index
        self.pitch_values = pitch_values or [-60.0, -45.2, -45.1]
        self.pitch_reads = 0

    def get_payload_index(self) -> str | None:
        return self.payload_index

    def get_gimbal_attitude(self) -> tuple[float | None, float | None, float | None]:
        index = min(self.pitch_reads, len(self.pitch_values) - 1)
        self.pitch_reads += 1
        return self.pitch_values[index], 0.0, -90.0


def _moving_payloads(mqtt: _FakeMQTTClient) -> list[dict]:
    return [
        item["payload"]
        for item in mqtt.client.published
        if item["payload"]["data"]["pitch_speed"] != 0
    ]


def test_public_api_exports_gimbal_pitch_symbols() -> None:
    import pydjimqtt

    assert pydjimqtt.GIMBAL_PITCH_MIN_DEG == -90.0
    assert pydjimqtt.GIMBAL_PITCH_MAX_DEG == 35.0
    assert pydjimqtt.DEFAULT_GIMBAL_PITCH_PROFILE.pitch_min == -90.0
    assert pydjimqtt.DEFAULT_GIMBAL_PITCH_PROFILE.pitch_max == 35.0
    assert callable(pydjimqtt.set_gimbal_pitch)
    assert callable(pydjimqtt.set_gimbal_pitch_async)
    assert pydjimqtt.GimbalPitchController is not None
    assert pydjimqtt.GimbalPitchResult is not None


def test_set_gimbal_pitch_clamps_out_of_range_target_and_returns_result() -> None:
    from pydjimqtt import set_gimbal_pitch

    mqtt = _FakeMQTTClient(pitch_values=[30.0, 34.8, 35.0])

    result = set_gimbal_pitch(mqtt, 60.0, pad_to_deadline=False)

    assert result.requested_pitch == 60.0
    assert result.target_pitch == 35.0
    assert result.clamped is True
    assert result.converged is True
    assert result.start_pitch == 30.0
    assert result.final_pitch == 34.8
    assert result.deadline_s == pytest.approx(7.308)
    assert _moving_payloads(mqtt)[0]["data"]["pitch_speed"] > 0


def test_set_gimbal_pitch_uses_negative_speed_when_target_is_lower() -> None:
    from pydjimqtt import set_gimbal_pitch

    mqtt = _FakeMQTTClient(pitch_values=[-30.0, -44.8, -45.0])

    result = set_gimbal_pitch(mqtt, -45.0, pad_to_deadline=False)

    assert result.converged is True
    assert _moving_payloads(mqtt)[0]["data"]["pitch_speed"] < 0


def test_pulse_sends_move_and_stop_commands_on_drc_down() -> None:
    from pydjimqtt import set_gimbal_pitch

    mqtt = _FakeMQTTClient(pitch_values=[-60.0, -45.2])

    set_gimbal_pitch(mqtt, -45.0, pad_to_deadline=False)

    assert len(mqtt.client.published) >= 2
    assert mqtt.client.published[-1]["qos"] == 0
    assert mqtt.client.published[-1]["topic"] == (
        "thing/product/9N9CN180011TJN/drc/down"
    )
    assert mqtt.client.published[-1]["payload"]["method"] == "drc_camera_screen_drag"
    assert mqtt.client.published[-1]["payload"]["data"] == {
        "payload_index": "88-0-0",
        "locked": False,
        "pitch_speed": 0,
        "yaw_speed": 0,
    }


def test_inside_tolerance_sends_no_move_command() -> None:
    from pydjimqtt import set_gimbal_pitch

    mqtt = _FakeMQTTClient(pitch_values=[-45.2])

    result = set_gimbal_pitch(mqtt, -45.0, pad_to_deadline=False)

    assert result.converged is True
    assert result.steps == 0
    assert _moving_payloads(mqtt) == []


def test_missing_payload_index_or_pitch_osd_raises_timeout() -> None:
    from pydjimqtt import set_gimbal_pitch

    with pytest.raises(TimeoutError, match="payload_index"):
        set_gimbal_pitch(
            _FakeMQTTClient(payload_index=None),
            -45.0,
            pad_to_deadline=False,
        )

    with pytest.raises(TimeoutError, match="gimbal pitch"):
        set_gimbal_pitch(
            _FakeMQTTClient(pitch_values=[None]),
            -45.0,
            pad_to_deadline=False,
        )


def test_disconnected_mqtt_client_raises_runtime_error() -> None:
    from pydjimqtt import set_gimbal_pitch

    mqtt = _FakeMQTTClient(pitch_values=[-45.2])
    mqtt.client = None

    with pytest.raises(RuntimeError, match="MQTT client is not connected"):
        set_gimbal_pitch(mqtt, -45.0, pad_to_deadline=False)


def test_set_gimbal_pitch_docstring_documents_limits_and_clamping() -> None:
    from pydjimqtt import set_gimbal_pitch

    doc = set_gimbal_pitch.__doc__ or ""

    assert "-90.0 <= target_pitch <= 35.0" in doc
    assert "Out-of-range targets are clamped" in doc
    assert "blocking" in doc


def test_set_gimbal_pitch_async_returns_future_without_waiting() -> None:
    from pydjimqtt import set_gimbal_pitch_async

    mqtt = _FakeMQTTClient(pitch_values=[-60.0, -45.2])
    sleep_started = threading.Event()
    release_sleep = threading.Event()

    def blocking_sleep(_seconds: float) -> None:
        sleep_started.set()
        release_sleep.wait(timeout=2.0)

    start = time.monotonic()
    future = set_gimbal_pitch_async(
        mqtt,
        -45.0,
        pad_to_deadline=False,
        sleep_fn=blocking_sleep,
    )

    assert isinstance(future, Future)
    assert time.monotonic() - start < 0.2
    assert sleep_started.wait(timeout=1.0)
    assert future.done() is False

    release_sleep.set()
    result = future.result(timeout=2.0)

    assert result.converged is True


def test_controller_set_pitch_async_returns_future() -> None:
    from pydjimqtt import GimbalPitchController

    controller = GimbalPitchController(
        _FakeMQTTClient(pitch_values=[-45.2]),
        sleep_fn=lambda _seconds: None,
    )

    future = controller.set_pitch_async(-45.0, pad_to_deadline=False)

    assert isinstance(future, Future)
    assert future.result(timeout=1.0).steps == 0


def test_async_errors_are_available_from_future_result() -> None:
    from pydjimqtt import set_gimbal_pitch_async

    future = set_gimbal_pitch_async(
        _FakeMQTTClient(payload_index=None),
        -45.0,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(TimeoutError, match="payload_index"):
        future.result(timeout=1.0)

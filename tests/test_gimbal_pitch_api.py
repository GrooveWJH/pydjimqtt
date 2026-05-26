from __future__ import annotations

import threading
import time
from dataclasses import replace

from pydjimqtt.gimbal.profile import DEFAULT_GIMBAL_PITCH_PROFILE
from gimbal_pitch_fakes import FakeMQTTClient, as_mqtt_client, moving_payloads


FAST_PROFILE = replace(
    DEFAULT_GIMBAL_PITCH_PROFILE,
    max_control_iterations=20,
    settle_seconds=0.0,
    observation_window_s=0.04,
    control_interval_s=0.001,
)


def test_public_api_exports_async_gimbal_pitch_symbols() -> None:
    import pydjimqtt

    assert pydjimqtt.GIMBAL_PITCH_MIN_DEG == -90.0
    assert pydjimqtt.GIMBAL_PITCH_MAX_DEG == 90.0
    assert pydjimqtt.DEFAULT_GIMBAL_PITCH_PROFILE.pitch_min == -90.0
    assert pydjimqtt.DEFAULT_GIMBAL_PITCH_PROFILE.pitch_max == 90.0
    assert callable(pydjimqtt.set_gimbal_pitch_async)
    assert not hasattr(pydjimqtt, "set_gimbal_pitch")
    assert pydjimqtt.GimbalPitchController is not None
    assert pydjimqtt.GimbalPitchResult is not None
    assert pydjimqtt.GimbalPitchTask is not None
    assert pydjimqtt.GimbalPitchTraceStep is not None
    assert pydjimqtt.GimbalPitchStatus.SUCCEEDED == "SUCCEEDED"
    assert callable(pydjimqtt.load_gimbal_pitch_profile)
    assert callable(pydjimqtt.save_gimbal_pitch_profile)


def test_builtin_profile_matches_real_machine_stream_defaults() -> None:
    profile = DEFAULT_GIMBAL_PITCH_PROFILE

    assert profile.proportional_gain == 2.0
    assert profile.min_speed == 5.0
    assert profile.max_speed == 40.0
    assert profile.near_target_speed == 2.5
    assert profile.near_target_error_deg == 4.0
    assert profile.settle_tolerance_deg == 1.0
    assert profile.settle_seconds == 0.06
    assert profile.confirm_reads == 3
    assert profile.control_interval_s == 0.08
    assert profile.observation_window_s == 0.22
    assert profile.stall_timeout_s == 1.2
    assert profile.max_control_iterations == 80
    assert profile.pad_to_deadline is False
    assert not hasattr(profile, "max_pulse_s")


def test_set_gimbal_pitch_async_returns_task_immediately_while_running() -> None:
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    mqtt = FakeMQTTClient(pitch_values=[-60.0, -45.2])
    sleep_started = threading.Event()
    release_sleep = threading.Event()

    def blocking_sleep(_seconds: float) -> None:
        sleep_started.set()
        release_sleep.wait(timeout=2.0)

    start = time.monotonic()
    task = set_gimbal_pitch_async(
        as_mqtt_client(mqtt),
        -45.0,
        profile=FAST_PROFILE,
        pad_to_deadline=False,
        sleep_fn=blocking_sleep,
    )

    assert time.monotonic() - start < 0.2
    assert task.status() == GimbalPitchStatus.RUNNING
    assert sleep_started.wait(timeout=1.0)
    assert task.status() == GimbalPitchStatus.RUNNING

    release_sleep.set()
    result = task.result(timeout=2.0)

    assert result.status == GimbalPitchStatus.SUCCEEDED
    assert task.status() == GimbalPitchStatus.SUCCEEDED


def test_proportional_planner_uses_higher_speed_for_larger_error() -> None:
    from pydjimqtt.gimbal.controller import PitchSpeedPlanner

    profile = replace(
        DEFAULT_GIMBAL_PITCH_PROFILE,
        proportional_gain=1.2,
        min_speed=4.0,
        max_speed=35.0,
        near_target_error_deg=3.0,
        near_target_speed=2.0,
    )
    planner = PitchSpeedPlanner(profile)

    large = planner.plan(current=0.0, target=40.0)
    small = planner.plan(current=0.0, target=2.0)

    assert abs(large) == 35.0
    assert abs(small) < abs(large)
    assert abs(small) >= profile.near_target_speed


def test_target_pitch_is_not_clamped_to_current_aircraft_limit() -> None:
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    mqtt = FakeMQTTClient(pitch_values=[30.0, 50.0, 59.7])

    result = set_gimbal_pitch_async(
        as_mqtt_client(mqtt),
        60.0,
        profile=FAST_PROFILE,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    ).result(timeout=1.0)

    assert result.requested_pitch == 60.0
    assert result.target_pitch == 60.0
    assert result.status == GimbalPitchStatus.SUCCEEDED
    assert result.converged is True
    assert result.final_pitch == 59.7
    assert moving_payloads(mqtt)[0]["data"]["pitch_speed"] > 0


def test_set_gimbal_pitch_async_loads_saved_profile_when_profile_is_none(monkeypatch) -> None:
    import pydjimqtt.gimbal.api as api
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    saved_profile = replace(
        FAST_PROFILE,
        proportional_gain=2.0,
        max_speed=30.0,
        min_speed=3.0,
        confirm_reads=1,
    )
    monkeypatch.setattr(api, "load_gimbal_pitch_profile", lambda _sn: saved_profile)
    mqtt = FakeMQTTClient(pitch_values=[30.0, 59.8])

    result = set_gimbal_pitch_async(
        as_mqtt_client(mqtt),
        60.0,
        profile=None,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    ).result(timeout=1.0)

    assert result.status == GimbalPitchStatus.SUCCEEDED
    moving = moving_payloads(mqtt)
    assert moving[0]["data"]["pitch_speed"] == 30.0


def test_unreachable_target_reports_physical_limit_without_hanging() -> None:
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    mqtt = FakeMQTTClient(pitch_values=[30.0, 34.5, 35.0, 35.0, 35.0, 35.0])

    result = set_gimbal_pitch_async(
        as_mqtt_client(mqtt),
        90.0,
        profile=FAST_PROFILE,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    ).result(timeout=1.0)

    assert result.status == GimbalPitchStatus.UNREACHABLE
    assert result.converged is False
    assert result.target_pitch == 90.0
    assert result.start_pitch == 30.0
    assert result.final_pitch == 35.0
    assert result.error == "physical_limit"


def test_no_pitch_progress_reports_failed_instead_of_physical_limit() -> None:
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    mqtt = FakeMQTTClient(pitch_values=[30.0, 30.0, 30.0, 30.0])

    result = set_gimbal_pitch_async(
        as_mqtt_client(mqtt),
        90.0,
        profile=FAST_PROFILE,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    ).result(timeout=1.0)

    assert result.status == GimbalPitchStatus.FAILED
    assert result.code == "no_progress"
    assert result.error == "gimbal pitch did not move toward target"


def test_final_confirmation_can_promote_late_target_arrival_to_success() -> None:
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    profile = replace(FAST_PROFILE, max_control_iterations=2, settle_tolerance_deg=0.6)
    mqtt = FakeMQTTClient(pitch_values=[60.0, -70.0, -87.9, -90.0])

    result = set_gimbal_pitch_async(
        as_mqtt_client(mqtt),
        -90.0,
        profile=profile,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    ).result(timeout=1.0)

    assert result.status == GimbalPitchStatus.SUCCEEDED
    assert result.final_pitch == -90.0
    assert result.error is None


def test_final_confirmation_uses_configured_confirm_reads() -> None:
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    profile = replace(
        FAST_PROFILE,
        max_control_iterations=1,
        settle_tolerance_deg=0.6,
        confirm_reads=2,
    )
    mqtt = FakeMQTTClient(pitch_values=[60.0, -80.0, -87.0, -90.0])

    result = set_gimbal_pitch_async(
        as_mqtt_client(mqtt),
        -90.0,
        profile=profile,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    ).result(timeout=1.0)

    assert result.status == GimbalPitchStatus.SUCCEEDED
    assert result.final_pitch == -90.0


def test_control_loop_waits_for_fresh_pitch_while_streaming() -> None:
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    profile = replace(
        FAST_PROFILE,
        max_control_iterations=1,
        settle_tolerance_deg=1.0,
        confirm_reads=1,
    )
    mqtt = FakeMQTTClient(
        pitch_values=[20.0, -90.0],
        stale_reads_after_publish=2,
    )

    result = set_gimbal_pitch_async(
        as_mqtt_client(mqtt),
        -90.0,
        profile=profile,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    ).result(timeout=1.0)

    assert result.status == GimbalPitchStatus.SUCCEEDED
    assert result.final_pitch == -90.0


def test_failed_preconditions_return_failed_result() -> None:
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    result = set_gimbal_pitch_async(
        as_mqtt_client(FakeMQTTClient(payload_index=None)),
        -45.0,
        profile=FAST_PROFILE,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    ).result(timeout=1.0)

    assert result.status == GimbalPitchStatus.FAILED
    assert result.error is not None
    assert "payload_index" in result.error


def test_disconnected_mqtt_returns_failed_result() -> None:
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    mqtt = FakeMQTTClient(pitch_values=[-45.2])
    mqtt.client = None

    result = set_gimbal_pitch_async(
        as_mqtt_client(mqtt),
        -45.0,
        profile=FAST_PROFILE,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    ).result(timeout=1.0)

    assert result.status == GimbalPitchStatus.FAILED
    assert result.code == "RuntimeError"
    assert result.error == "MQTT client is not connected"


def test_stream_control_sends_move_and_final_stop_commands_on_drc_down() -> None:
    from pydjimqtt import set_gimbal_pitch_async

    mqtt = FakeMQTTClient(pitch_values=[-60.0, -45.2])

    set_gimbal_pitch_async(
        as_mqtt_client(mqtt),
        -45.0,
        profile=FAST_PROFILE,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    ).result(timeout=1.0)

    assert mqtt.client is not None
    assert len(mqtt.client.published) >= 2
    assert mqtt.client.published[-1]["qos"] == 0
    assert mqtt.client.published[-1]["topic"] == ("thing/product/9N9CN180011TJN/drc/down")
    assert mqtt.client.published[-1]["payload"]["method"] == "drc_camera_screen_drag"
    assert mqtt.client.published[-1]["payload"]["data"] == {
        "payload_index": "88-0-0",
        "locked": False,
        "pitch_speed": 0,
        "yaw_speed": 0,
    }


def test_multi_step_control_streams_motion_without_intermediate_stop() -> None:
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    profile = replace(
        FAST_PROFILE,
        max_control_iterations=10,
        confirm_reads=1,
    )
    mqtt = FakeMQTTClient(pitch_values=[50.0, 20.0, -10.0, -39.5, -39.5])

    result = set_gimbal_pitch_async(
        as_mqtt_client(mqtt),
        -40.0,
        profile=profile,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    ).result(timeout=1.0)

    assert result.status == GimbalPitchStatus.SUCCEEDED
    assert mqtt.client is not None
    speeds = [
        item["payload"]["data"]["pitch_speed"]
        for item in mqtt.client.published
        if item["payload"]["method"] == "drc_camera_screen_drag"
    ]
    assert speeds.count(0) == 1
    assert speeds[-1] == 0


def test_result_exposes_stream_control_trace() -> None:
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    mqtt = FakeMQTTClient(pitch_values=[70.0, 57.0, 42.0, 29.8])

    result = set_gimbal_pitch_async(
        as_mqtt_client(mqtt),
        30.0,
        profile=FAST_PROFILE,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    ).result(timeout=1.0)

    assert result.status == GimbalPitchStatus.SUCCEEDED
    assert result.trace
    assert result.trace[0].start_pitch == 70.0
    assert result.trace[0].end_pitch == 57.0
    assert result.trace[0].commanded_speed < 0.0
    assert result.trace[-1].stopped is True


def test_inside_tolerance_sends_no_move_command() -> None:
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    mqtt = FakeMQTTClient(pitch_values=[-45.2])

    result = set_gimbal_pitch_async(
        as_mqtt_client(mqtt),
        -45.0,
        profile=FAST_PROFILE,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    ).result(timeout=1.0)

    assert result.status == GimbalPitchStatus.SUCCEEDED
    assert result.steps == 0
    assert moving_payloads(mqtt) == []


def test_task_status_matches_finished_result_status() -> None:
    from pydjimqtt import GimbalPitchStatus, set_gimbal_pitch_async

    task = set_gimbal_pitch_async(
        as_mqtt_client(FakeMQTTClient(pitch_values=[None])),
        -45.0,
        profile=FAST_PROFILE,
        pad_to_deadline=False,
        sleep_fn=lambda _seconds: None,
    )
    result = task.result(timeout=1.0)

    assert result.status == GimbalPitchStatus.FAILED
    assert task.status() == GimbalPitchStatus.FAILED

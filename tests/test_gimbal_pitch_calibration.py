from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

from pydjimqtt.gimbal.calibration import (
    GimbalPitchCalibrationSample,
    GimbalPitchCalibrationStatus,
    build_calibrated_profile,
    classify_limit_or_failure,
    calibrate_gimbal_pitch,
)
from gimbal_pitch_fakes import FakeMQTTClient, as_mqtt_client


def _load_tool() -> ModuleType:
    tool_path = Path(__file__).resolve().parents[1] / "tools" / "calibrate_gimbal_pitch.py"
    spec = importlib.util.spec_from_file_location("calibrate_gimbal_pitch", tool_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_calibrated_profile_uses_measured_limits_and_aggressive_gain() -> None:
    samples = [
        GimbalPitchCalibrationSample(
            direction="down",
            speed=-20.0,
            duration_s=1.0,
            start_pitch=0.0,
            end_pitch=-30.0,
            elapsed_s=1.1,
        ),
        GimbalPitchCalibrationSample(
            direction="up",
            speed=20.0,
            duration_s=1.0,
            start_pitch=0.0,
            end_pitch=22.0,
            elapsed_s=1.1,
        ),
    ]

    profile = build_calibrated_profile(
        physical_min=-90.0,
        physical_max=35.0,
        samples=samples,
    )

    assert profile.pitch_min == -90.0
    assert profile.pitch_max == 90.0
    assert profile.proportional_gain > 1.0
    assert profile.max_speed >= 35.0
    assert profile.proportional_gain >= 1.8
    assert profile.max_control_iterations == 80
    assert profile.observation_window_s <= 0.22
    assert profile.model.velocity_down_per_speed > profile.model.velocity_up_per_speed


def test_build_calibrated_profile_ignores_limit_stall_samples_for_velocity_model() -> None:
    samples = [
        GimbalPitchCalibrationSample(
            direction="up",
            speed=40.0,
            duration_s=0.8,
            start_pitch=-90.0,
            end_pitch=-61.0,
            elapsed_s=0.9,
        ),
        GimbalPitchCalibrationSample(
            direction="up",
            speed=40.0,
            duration_s=0.8,
            start_pitch=66.9,
            end_pitch=70.0,
            elapsed_s=0.9,
        ),
        GimbalPitchCalibrationSample(
            direction="up",
            speed=40.0,
            duration_s=0.8,
            start_pitch=70.0,
            end_pitch=70.0,
            elapsed_s=0.9,
        ),
        GimbalPitchCalibrationSample(
            direction="down",
            speed=-40.0,
            duration_s=0.8,
            start_pitch=0.0,
            end_pitch=-28.0,
            elapsed_s=0.9,
        ),
        GimbalPitchCalibrationSample(
            direction="down",
            speed=-40.0,
            duration_s=0.8,
            start_pitch=-90.0,
            end_pitch=-90.0,
            elapsed_s=0.9,
        ),
    ]

    profile = build_calibrated_profile(
        physical_min=-90.0,
        physical_max=70.0,
        samples=samples,
    )

    assert profile.model.velocity_up_per_speed > 0.8
    assert profile.model.velocity_down_per_speed > 0.8


def test_classify_limit_or_failure_separates_limit_from_no_motion() -> None:
    assert (
        classify_limit_or_failure(start_pitch=30.0, final_pitch=35.0, target_pitch=90.0)
        == GimbalPitchCalibrationStatus.PHYSICAL_LIMIT
    )
    assert (
        classify_limit_or_failure(start_pitch=30.0, final_pitch=30.0, target_pitch=90.0)
        == GimbalPitchCalibrationStatus.FAILED
    )


def test_calibration_cli_requires_yes_before_motion(capsys) -> None:
    tool = _load_tool()
    args = SimpleNamespace(yes=False)

    assert tool._ensure_confirmed(args) is False
    captured = capsys.readouterr()
    assert "--yes" in captured.out


def test_calibrate_gimbal_pitch_builds_profile_from_measured_steps() -> None:
    mqtt = FakeMQTTClient(
        pitch_values=[
            0.0,
            -18.0,
            -42.0,
            -70.0,
            -90.0,
            -90.0,
            -64.0,
            -33.0,
            4.0,
            35.0,
            35.0,
        ]
    )

    result = calibrate_gimbal_pitch(
        as_mqtt_client(mqtt),
        payload_index="88-0-0",
        probe_duration_s=0.001,
        settle_s=0.0,
        sleep_fn=lambda _seconds: None,
    )

    assert result.status == GimbalPitchCalibrationStatus.SUCCEEDED
    assert result.physical_min <= -90.0
    assert result.physical_max >= 35.0
    assert len(result.samples) >= 4
    assert result.profile.max_speed >= 35.0
    assert any(sample.direction == "up" and sample.speed >= 35.0 for sample in result.samples)
    assert result.reached_lower_limit is True
    assert result.reached_upper_limit is True

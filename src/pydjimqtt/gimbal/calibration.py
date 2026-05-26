from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

from ..core import MQTTClient
from .io import send_screen_drag_pulse
from .profile import (
    DEFAULT_GIMBAL_PITCH_PROFILE,
    GimbalPitchProfile,
    PitchPlantModel,
)


class GimbalPitchCalibrationStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    PHYSICAL_LIMIT = "PHYSICAL_LIMIT"
    FAILED = "FAILED"


@dataclass(frozen=True)
class GimbalPitchCalibrationSample:
    direction: str
    speed: float
    duration_s: float
    start_pitch: float
    end_pitch: float
    elapsed_s: float

    @property
    def delta(self) -> float:
        return self.end_pitch - self.start_pitch

    @property
    def velocity_per_speed(self) -> float:
        denominator = abs(self.speed) * max(self.duration_s, 0.001)
        return abs(self.delta) / denominator


@dataclass(frozen=True)
class GimbalPitchCalibrationResult:
    status: GimbalPitchCalibrationStatus
    profile: GimbalPitchProfile
    physical_min: float
    physical_max: float
    samples: list[GimbalPitchCalibrationSample]
    elapsed_s: float
    reached_lower_limit: bool
    reached_upper_limit: bool
    error: str | None = None


def classify_limit_or_failure(
    *,
    start_pitch: float,
    final_pitch: float,
    target_pitch: float,
    movement_threshold_deg: float = 0.5,
) -> GimbalPitchCalibrationStatus:
    target_direction = 1.0 if target_pitch >= start_pitch else -1.0
    progress = (final_pitch - start_pitch) * target_direction
    if progress >= movement_threshold_deg:
        return GimbalPitchCalibrationStatus.PHYSICAL_LIMIT
    return GimbalPitchCalibrationStatus.FAILED


def build_calibrated_profile(
    *,
    physical_min: float,
    physical_max: float,
    samples: list[GimbalPitchCalibrationSample],
) -> GimbalPitchProfile:
    up_velocity = _robust_velocity(
        samples,
        direction="up",
        fallback=DEFAULT_GIMBAL_PITCH_PROFILE.model.velocity_up_per_speed,
    )
    down_velocity = _robust_velocity(
        samples,
        direction="down",
        fallback=DEFAULT_GIMBAL_PITCH_PROFILE.model.velocity_down_per_speed,
    )
    max_speed = 40.0
    return GimbalPitchProfile(
        pitch_min=DEFAULT_GIMBAL_PITCH_PROFILE.pitch_min,
        pitch_max=DEFAULT_GIMBAL_PITCH_PROFILE.pitch_max,
        model=PitchPlantModel(
            velocity_up_per_speed=round(up_velocity, 3),
            velocity_down_per_speed=round(down_velocity, 3),
            latency=0.08,
            max_effective_speed=max_speed,
        ),
        settle_seconds=0.06,
        settle_tolerance_deg=1.0,
        adaptive_enabled=True,
        adaptive_smoothing=0.12,
        stall_min_progress_deg=0.2,
        proportional_gain=2.0,
        min_speed=5.0,
        max_speed=max_speed,
        near_target_speed=2.5,
        near_target_error_deg=4.0,
        confirm_reads=3,
        max_control_iterations=80,
        observation_window_s=0.22,
        control_interval_s=0.08,
        stall_timeout_s=1.2,
        pad_to_deadline=False,
        deadline_s=0.0,
    )


def _robust_velocity(
    samples: list[GimbalPitchCalibrationSample],
    *,
    direction: str,
    fallback: float,
) -> float:
    values = [
        sample.velocity_per_speed
        for sample in samples
        if sample.direction == direction
        and abs(sample.delta) >= 5.0
        and sample.velocity_per_speed >= 0.15
    ]
    if not values:
        return fallback
    values.sort()
    midpoint = len(values) // 2
    if len(values) % 2 == 1:
        return round(values[midpoint], 3)
    return round((values[midpoint - 1] + values[midpoint]) / 2.0, 3)


def _read_pitch(mqtt_client: MQTTClient) -> float:
    pitch, _roll, _yaw = mqtt_client.get_gimbal_attitude()
    if pitch is None:
        raise TimeoutError("gimbal pitch is not available from camera OSD")
    return float(pitch)


def measure_pitch_step(
    mqtt_client: MQTTClient,
    *,
    payload_index: str,
    speed: float,
    duration_s: float,
    settle_s: float,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> GimbalPitchCalibrationSample:
    start = _read_pitch(mqtt_client)
    start_time = time.monotonic()
    send_screen_drag_pulse(
        mqtt_client,
        payload_index=payload_index,
        pitch_speed=speed,
        duration=duration_s,
        sleep_fn=sleep_fn,
    )
    sleep_fn(settle_s)
    end = _read_pitch(mqtt_client)
    return GimbalPitchCalibrationSample(
        direction="up" if speed > 0 else "down",
        speed=speed,
        duration_s=duration_s,
        start_pitch=start,
        end_pitch=end,
        elapsed_s=round(time.monotonic() - start_time, 3),
    )


def _probe_limit(
    mqtt_client: MQTTClient,
    *,
    payload_index: str,
    speed: float,
    max_steps: int = 8,
    duration_s: float = 0.8,
    settle_s: float = 0.15,
    stall_threshold_deg: float = 0.5,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[list[GimbalPitchCalibrationSample], bool]:
    samples: list[GimbalPitchCalibrationSample] = []
    stalled = 0
    for _ in range(max_steps):
        sample = measure_pitch_step(
            mqtt_client,
            payload_index=payload_index,
            speed=speed,
            duration_s=duration_s,
            settle_s=settle_s,
            sleep_fn=sleep_fn,
        )
        samples.append(sample)
        if abs(sample.delta) < stall_threshold_deg:
            stalled += 1
        else:
            stalled = 0
        if stalled >= 1:
            return samples, True
    return samples, False


def calibrate_gimbal_pitch(
    mqtt_client: MQTTClient,
    *,
    payload_index: str,
    probe_duration_s: float = 0.8,
    settle_s: float = 0.15,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> GimbalPitchCalibrationResult:
    start_time = time.monotonic()
    samples: list[GimbalPitchCalibrationSample] = []
    try:
        mqtt_client.wait_for_gimbal_attitude(timeout=10.0, poll_interval=0.1)
        down_samples, reached_lower = _probe_limit(
            mqtt_client,
            payload_index=payload_index,
            speed=-40.0,
            duration_s=probe_duration_s,
            settle_s=settle_s,
            sleep_fn=sleep_fn,
        )
        samples.extend(down_samples)
        up_samples, reached_upper = _probe_limit(
            mqtt_client,
            payload_index=payload_index,
            speed=40.0,
            duration_s=probe_duration_s,
            settle_s=settle_s,
            sleep_fn=sleep_fn,
        )
        samples.extend(up_samples)
        pitches = [sample.start_pitch for sample in samples] + [
            sample.end_pitch for sample in samples
        ]
        physical_min = min(pitches)
        physical_max = max(pitches)
        profile = build_calibrated_profile(
            physical_min=physical_min,
            physical_max=physical_max,
            samples=samples,
        )
        return GimbalPitchCalibrationResult(
            status=GimbalPitchCalibrationStatus.SUCCEEDED,
            profile=profile,
            physical_min=physical_min,
            physical_max=physical_max,
            samples=samples,
            elapsed_s=round(time.monotonic() - start_time, 3),
            reached_lower_limit=reached_lower,
            reached_upper_limit=reached_upper,
        )
    except Exception as exc:
        return GimbalPitchCalibrationResult(
            status=GimbalPitchCalibrationStatus.FAILED,
            profile=DEFAULT_GIMBAL_PITCH_PROFILE,
            physical_min=0.0,
            physical_max=0.0,
            samples=samples,
            elapsed_s=round(time.monotonic() - start_time, 3),
            reached_lower_limit=False,
            reached_upper_limit=False,
            error=str(exc),
        )

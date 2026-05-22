from __future__ import annotations

from dataclasses import dataclass


GIMBAL_PITCH_MIN_DEG = -90.0
GIMBAL_PITCH_MAX_DEG = 35.0


@dataclass(frozen=True)
class PitchPlantModel:
    velocity_up_per_speed: float
    velocity_down_per_speed: float
    latency: float
    max_effective_speed: float

    def velocity_for_delta(self, delta: float) -> float:
        if delta >= 0:
            return self.velocity_up_per_speed
        return self.velocity_down_per_speed


@dataclass(frozen=True)
class GimbalPitchProfile:
    pitch_min: float
    pitch_max: float
    model: PitchPlantModel
    target_total_time_s: float
    settle_seconds: float
    coarse_speed: float
    fine_speed: float
    fine_error_deg: float
    settle_tolerance_deg: float
    duration_scale_up: float
    duration_scale_down: float
    min_pulse_s: float
    max_pulse_s: float
    max_pulses: int
    pad_to_deadline: bool
    adaptive_enabled: bool
    adaptive_smoothing: float


DEFAULT_GIMBAL_PITCH_PROFILE = GimbalPitchProfile(
    # Confirmed/accepted safe pitch range for this gimbal profile:
    # -90.0 <= target_pitch <= 35.0 degrees.
    pitch_min=GIMBAL_PITCH_MIN_DEG,
    pitch_max=GIMBAL_PITCH_MAX_DEG,
    model=PitchPlantModel(
        velocity_up_per_speed=0.766,
        velocity_down_per_speed=0.747,
        latency=0.486,
        max_effective_speed=20.0,
    ),
    target_total_time_s=7.308,
    settle_seconds=0.606,
    coarse_speed=20.0,
    fine_speed=10.0,
    fine_error_deg=6.0,
    settle_tolerance_deg=0.6,
    duration_scale_up=0.92,
    duration_scale_down=0.92,
    min_pulse_s=0.08,
    max_pulse_s=0.45,
    max_pulses=10,
    pad_to_deadline=True,
    adaptive_enabled=True,
    adaptive_smoothing=0.18,
)

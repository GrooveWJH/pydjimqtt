from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .profile import GimbalPitchProfile


def clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


@dataclass(frozen=True)
class PitchObservation:
    speed: float
    duration: float
    actual_delta: float


class PitchSpeedPlanner:
    def __init__(self, profile: GimbalPitchProfile) -> None:
        self.profile = profile

    def plan(self, *, current: float, target: float) -> float:
        error = target - current
        if abs(error) <= self.profile.settle_tolerance_deg:
            return 0.0

        speed_limit = min(abs(self.profile.max_speed), abs(self.profile.model.max_effective_speed))
        proportional_speed = abs(error) * self.profile.proportional_gain
        floor_speed = (
            self.profile.near_target_speed
            if abs(error) <= self.profile.near_target_error_deg
            else self.profile.min_speed
        )
        speed = math.copysign(
            clamp(proportional_speed, floor_speed, speed_limit),
            error,
        )
        return round(speed, 3)


def update_profile_from_observation(
    profile: GimbalPitchProfile,
    observation: PitchObservation,
) -> GimbalPitchProfile:
    if not profile.adaptive_enabled:
        return profile
    denominator = abs(observation.speed) * observation.duration
    if denominator <= 0 or abs(observation.actual_delta) < 0.5:
        return profile
    if math.copysign(1.0, observation.speed) != math.copysign(1.0, observation.actual_delta):
        return profile

    measured = abs(observation.actual_delta) / denominator
    smoothing = clamp(profile.adaptive_smoothing, 0.0, 1.0)
    model = profile.model

    if observation.speed > 0:
        current = model.velocity_up_per_speed
        model = replace(
            model,
            velocity_up_per_speed=round(
                (1.0 - smoothing) * current + smoothing * measured,
                3,
            ),
        )
    else:
        current = model.velocity_down_per_speed
        model = replace(
            model,
            velocity_down_per_speed=round(
                (1.0 - smoothing) * current + smoothing * measured,
                3,
            ),
        )
    return replace(profile, model=model)

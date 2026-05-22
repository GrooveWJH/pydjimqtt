from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .profile import GimbalPitchProfile


def clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


@dataclass(frozen=True)
class PitchCommand:
    speed: float
    duration: float
    expected_delta: float


@dataclass(frozen=True)
class PitchObservation:
    speed: float
    duration: float
    actual_delta: float


class PitchPulsePlanner:
    def __init__(self, profile: GimbalPitchProfile) -> None:
        self.profile = profile

    def plan(self, *, current: float, target: float) -> PitchCommand | None:
        error = target - current
        if abs(error) <= self.profile.settle_tolerance_deg:
            return None

        velocity = self.profile.model.velocity_for_delta(error)
        if velocity <= 0:
            return None

        speed_limit = min(
            abs(self.profile.coarse_speed),
            abs(self.profile.model.max_effective_speed),
        )
        speed = math.copysign(max(speed_limit, 1.0), error)
        raw_duration = abs(error) / (velocity * abs(speed))
        scale = (
            self.profile.duration_scale_up
            if error >= 0
            else self.profile.duration_scale_down
        )
        duration = clamp(
            raw_duration * scale,
            self.profile.min_pulse_s,
            self.profile.max_pulse_s,
        )
        expected_delta = math.copysign(velocity * abs(speed) * duration, error)
        return PitchCommand(
            speed=round(speed, 3),
            duration=round(duration, 3),
            expected_delta=round(expected_delta, 3),
        )


def update_profile_from_observation(
    profile: GimbalPitchProfile,
    observation: PitchObservation,
) -> GimbalPitchProfile:
    if not profile.adaptive_enabled:
        return profile
    denominator = abs(observation.speed) * observation.duration
    if denominator <= 0 or abs(observation.actual_delta) < 0.5:
        return profile
    if math.copysign(1.0, observation.speed) != math.copysign(
        1.0, observation.actual_delta
    ):
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

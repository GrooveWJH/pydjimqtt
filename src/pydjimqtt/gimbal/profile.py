from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GIMBAL_PITCH_MIN_DEG = -90.0
GIMBAL_PITCH_MAX_DEG = 90.0


@dataclass(frozen=True)
class PitchPlantModel:
    velocity_up_per_speed: float
    velocity_down_per_speed: float
    latency: float
    max_effective_speed: float


@dataclass(frozen=True)
class GimbalPitchProfile:
    pitch_min: float
    pitch_max: float
    model: PitchPlantModel
    settle_seconds: float
    settle_tolerance_deg: float
    adaptive_enabled: bool
    adaptive_smoothing: float
    stall_min_progress_deg: float
    proportional_gain: float
    min_speed: float
    max_speed: float
    near_target_speed: float
    near_target_error_deg: float
    confirm_reads: int
    max_control_iterations: int
    observation_window_s: float
    control_interval_s: float
    stall_timeout_s: float
    pad_to_deadline: bool
    deadline_s: float


def _default_profile_dir() -> Path:
    return Path.home() / ".config" / "pydjimqtt" / "gimbal_profiles"


def _profile_path(gateway_sn: str, config_dir: Path | None = None) -> Path:
    return (config_dir or _default_profile_dir()) / f"{gateway_sn}.json"


def _profile_to_dict(profile: GimbalPitchProfile) -> dict[str, Any]:
    return {
        "pitch_min": profile.pitch_min,
        "pitch_max": profile.pitch_max,
        "model": {
            "velocity_up_per_speed": profile.model.velocity_up_per_speed,
            "velocity_down_per_speed": profile.model.velocity_down_per_speed,
            "latency": profile.model.latency,
            "max_effective_speed": profile.model.max_effective_speed,
        },
        "settle_seconds": profile.settle_seconds,
        "settle_tolerance_deg": profile.settle_tolerance_deg,
        "adaptive_enabled": profile.adaptive_enabled,
        "adaptive_smoothing": profile.adaptive_smoothing,
        "stall_min_progress_deg": profile.stall_min_progress_deg,
        "proportional_gain": profile.proportional_gain,
        "min_speed": profile.min_speed,
        "max_speed": profile.max_speed,
        "near_target_speed": profile.near_target_speed,
        "near_target_error_deg": profile.near_target_error_deg,
        "confirm_reads": profile.confirm_reads,
        "max_control_iterations": profile.max_control_iterations,
        "observation_window_s": profile.observation_window_s,
        "control_interval_s": profile.control_interval_s,
        "stall_timeout_s": profile.stall_timeout_s,
        "pad_to_deadline": profile.pad_to_deadline,
        "deadline_s": profile.deadline_s,
    }


def _profile_from_dict(data: dict[str, Any]) -> GimbalPitchProfile:
    model = data.get("model", {})
    deadline_s = float(data.get("deadline_s", data.get("target_total_time_s", 0.0)))
    return GimbalPitchProfile(
        pitch_min=float(data["pitch_min"]),
        pitch_max=float(data["pitch_max"]),
        model=PitchPlantModel(
            velocity_up_per_speed=float(model["velocity_up_per_speed"]),
            velocity_down_per_speed=float(model["velocity_down_per_speed"]),
            latency=float(model.get("latency", 0.0)),
            max_effective_speed=float(model["max_effective_speed"]),
        ),
        settle_seconds=float(data["settle_seconds"]),
        settle_tolerance_deg=float(data["settle_tolerance_deg"]),
        adaptive_enabled=bool(data["adaptive_enabled"]),
        adaptive_smoothing=float(data["adaptive_smoothing"]),
        stall_min_progress_deg=float(data["stall_min_progress_deg"]),
        proportional_gain=float(data["proportional_gain"]),
        min_speed=float(data["min_speed"]),
        max_speed=float(data["max_speed"]),
        near_target_speed=float(data["near_target_speed"]),
        near_target_error_deg=float(data["near_target_error_deg"]),
        confirm_reads=int(data["confirm_reads"]),
        max_control_iterations=int(data.get("max_control_iterations", data.get("max_pulses", 80))),
        observation_window_s=float(
            data.get("observation_window_s", data.get("post_pulse_observation_s", 0.22))
        ),
        control_interval_s=float(data.get("control_interval_s", 0.08)),
        stall_timeout_s=float(data.get("stall_timeout_s", 1.2)),
        pad_to_deadline=bool(data.get("pad_to_deadline", False)),
        deadline_s=deadline_s,
    )


def save_gimbal_pitch_profile(
    gateway_sn: str,
    profile: GimbalPitchProfile,
    metadata: dict[str, Any] | None = None,
    *,
    config_dir: Path | None = None,
) -> Path:
    path = _profile_path(gateway_sn, config_dir=config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 2,
        "gateway_sn": gateway_sn,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
        "profile": _profile_to_dict(profile),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_gimbal_pitch_profile(
    gateway_sn: str,
    *,
    config_dir: Path | None = None,
) -> GimbalPitchProfile | None:
    path = _profile_path(gateway_sn, config_dir=config_dir)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if int(payload.get("schema_version", 0)) not in {1, 2}:
        return None
    return _profile_from_dict(payload["profile"])


DEFAULT_GIMBAL_PITCH_PROFILE = GimbalPitchProfile(
    # API intent range. Physical aircraft limits are detected by feedback.
    pitch_min=GIMBAL_PITCH_MIN_DEG,
    pitch_max=GIMBAL_PITCH_MAX_DEG,
    model=PitchPlantModel(
        velocity_up_per_speed=0.872,
        velocity_down_per_speed=0.872,
        latency=0.08,
        max_effective_speed=40.0,
    ),
    settle_seconds=0.06,
    settle_tolerance_deg=1.0,
    adaptive_enabled=True,
    adaptive_smoothing=0.12,
    stall_min_progress_deg=0.2,
    proportional_gain=2.0,
    min_speed=5.0,
    max_speed=40.0,
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

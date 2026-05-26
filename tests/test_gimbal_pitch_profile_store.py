from __future__ import annotations

import json
from dataclasses import replace

from pydjimqtt.gimbal.profile import (
    DEFAULT_GIMBAL_PITCH_PROFILE,
    load_gimbal_pitch_profile,
    save_gimbal_pitch_profile,
)


def test_save_and_load_gateway_specific_gimbal_pitch_profile(tmp_path) -> None:
    profile = replace(
        DEFAULT_GIMBAL_PITCH_PROFILE,
        proportional_gain=1.8,
        min_speed=5.0,
        max_speed=38.0,
        near_target_speed=3.0,
        near_target_error_deg=4.0,
        confirm_reads=3,
    )

    saved = save_gimbal_pitch_profile(
        "SN123",
        profile,
        metadata={"physical_min": -90.0, "physical_max": 35.0},
        config_dir=tmp_path,
    )
    loaded = load_gimbal_pitch_profile("SN123", config_dir=tmp_path)

    assert saved.name == "SN123.json"
    assert loaded == profile
    assert load_gimbal_pitch_profile("OTHER", config_dir=tmp_path) is None
    payload = json.loads(saved.read_text(encoding="utf-8"))
    assert payload["created_at"]
    assert payload["schema_version"] == 2
    assert "max_control_iterations" in payload["profile"]
    assert "max_pulses" not in payload["profile"]


def test_load_legacy_profile_migrates_pulse_fields_to_stream_fields(tmp_path) -> None:
    saved = save_gimbal_pitch_profile("LEGACY", DEFAULT_GIMBAL_PITCH_PROFILE, config_dir=tmp_path)
    payload = json.loads(saved.read_text(encoding="utf-8"))
    payload["schema_version"] = 1
    payload["profile"]["target_total_time_s"] = 7.3
    payload["profile"]["max_pulses"] = 50
    payload["profile"]["post_pulse_observation_s"] = 0.28
    payload["profile"].pop("deadline_s")
    payload["profile"].pop("max_control_iterations")
    payload["profile"].pop("observation_window_s")
    saved.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_gimbal_pitch_profile("LEGACY", config_dir=tmp_path)

    assert loaded is not None
    assert loaded.deadline_s == 7.3
    assert loaded.max_control_iterations == 50
    assert loaded.observation_window_s == 0.28

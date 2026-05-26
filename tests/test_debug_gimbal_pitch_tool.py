from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace


def _load_tool() -> ModuleType:
    tool_path = Path(__file__).resolve().parents[1] / "tools" / "debug_gimbal_pitch.py"
    spec = importlib.util.spec_from_file_location("debug_gimbal_pitch", tool_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fast_mode_uses_low_latency_profile_without_deadline_padding() -> None:
    tool = _load_tool()
    args = SimpleNamespace(fast=True)

    profile, pad_to_deadline = tool._profile_from_args(args)

    assert pad_to_deadline is False
    assert profile.pad_to_deadline is False
    assert profile.settle_seconds < tool.DEFAULT_GIMBAL_PITCH_PROFILE.settle_seconds
    assert profile.max_control_iterations < tool.DEFAULT_GIMBAL_PITCH_PROFILE.max_control_iterations
    assert profile.proportional_gain >= 2.0
    assert profile.max_speed >= 40.0


def test_default_mode_keeps_library_profile_and_padding_policy() -> None:
    tool = _load_tool()
    args = SimpleNamespace(fast=False, no_profile=True, gateway_sn="SN123")

    profile, pad_to_deadline = tool._profile_from_args(args)

    assert profile is tool.DEFAULT_GIMBAL_PITCH_PROFILE
    assert pad_to_deadline is None


def test_default_mode_loads_saved_profile_before_builtin_default(monkeypatch) -> None:
    tool = _load_tool()
    saved_profile = tool.replace(
        tool.DEFAULT_GIMBAL_PITCH_PROFILE,
        proportional_gain=2.4,
    )
    monkeypatch.setattr(tool, "load_gimbal_pitch_profile", lambda _sn: saved_profile)
    args = SimpleNamespace(fast=False, no_profile=False, gateway_sn="SN123")

    profile, pad_to_deadline = tool._profile_from_args(args)

    assert profile is saved_profile
    assert pad_to_deadline is None

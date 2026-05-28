from __future__ import annotations

import time
from typing import Any, Callable

from ...core import MQTTClient
from ..controller import clamp
from ..models import GimbalPitchResult, GimbalPitchStatus, GimbalPitchTraceStep
from ..profile import GimbalPitchProfile
from .result_factory import failure_result, pitch_result
from .stream_control import run_stream_control, within_tolerance


def run_pitch_control(
    mqtt_client: MQTTClient,
    requested: float,
    profile: GimbalPitchProfile,
    payload_index: str | None,
    sleep_fn: Callable[[float], Any],
    pad_to_deadline: bool | None,
    controller_factory,
) -> GimbalPitchResult:
    start_time = time.monotonic()
    target = clamp(requested, profile.pitch_min, profile.pitch_max)
    controller = controller_factory(
        mqtt_client, profile=profile, payload_index=payload_index, sleep_fn=sleep_fn
    )
    start_pitch: float | None = None
    current: float | None = None
    steps = 0
    total_progress = 0.0
    trace: list[GimbalPitchTraceStep] = []

    try:
        if mqtt_client.client is None:
            raise RuntimeError("MQTT client is not connected")
        start_pitch = current = controller._read_pitch()
        stream_result = run_stream_control(
            mqtt_client=mqtt_client,
            controller=controller,
            payload_index=controller._payload_index(),
            target=target,
            current=current,
            profile=profile,
            start_time=start_time,
            sleep_fn=sleep_fn,
        )
        current = stream_result.current
        profile = stream_result.profile
        steps = stream_result.steps
        total_progress = stream_result.total_progress
        trace = stream_result.trace
        elapsed = apply_deadline_padding(profile, pad_to_deadline, start_time, sleep_fn)
        current, elapsed = confirm_final_pitch(
            controller, current, target, profile, start_time, sleep_fn
        )
        return _final_result(
            requested, target, start_pitch, current, steps, elapsed, profile, trace, total_progress
        )
    except Exception as exc:
        return failure_result(
            requested=requested,
            target=target,
            start_time=start_time,
            deadline_s=profile.deadline_s,
            error=exc,
            start_pitch=start_pitch,
            final_pitch=current,
            steps=steps,
            trace=tuple(trace),
        )


def apply_deadline_padding(profile, pad_to_deadline, start_time, sleep_fn) -> float:
    elapsed = time.monotonic() - start_time
    should_pad = profile.pad_to_deadline if pad_to_deadline is None else pad_to_deadline
    if should_pad and elapsed < profile.deadline_s:
        sleep_fn(profile.deadline_s - elapsed)
        return time.monotonic() - start_time
    return elapsed


def confirm_final_pitch(
    controller, current, target, profile, start_time, sleep_fn
) -> tuple[float, float]:
    elapsed = time.monotonic() - start_time
    for _ in range(max(1, profile.confirm_reads)):
        if within_tolerance(current, target, profile.settle_tolerance_deg):
            break
        sleep_fn(profile.settle_seconds)
        current = controller._read_pitch()
        elapsed = time.monotonic() - start_time
    return current, elapsed


def _final_result(
    requested: float,
    target: float,
    start_pitch: float,
    current: float,
    steps: int,
    elapsed: float,
    profile: GimbalPitchProfile,
    trace: list[GimbalPitchTraceStep],
    total_progress: float,
) -> GimbalPitchResult:
    if within_tolerance(current, target, profile.settle_tolerance_deg):
        return pitch_result(
            status=GimbalPitchStatus.SUCCEEDED,
            code="ok",
            requested=requested,
            target=target,
            start_pitch=start_pitch,
            final_pitch=current,
            steps=steps,
            elapsed_s=elapsed,
            deadline_s=profile.deadline_s,
            trace=trace,
        )
    if total_progress < profile.stall_min_progress_deg:
        return pitch_result(
            status=GimbalPitchStatus.FAILED,
            code="no_progress",
            requested=requested,
            target=target,
            start_pitch=start_pitch,
            final_pitch=current,
            steps=steps,
            elapsed_s=elapsed,
            deadline_s=profile.deadline_s,
            trace=trace,
            error="gimbal pitch did not move toward target",
        )
    return pitch_result(
        status=GimbalPitchStatus.UNREACHABLE,
        code="physical_limit",
        requested=requested,
        target=target,
        start_pitch=start_pitch,
        final_pitch=current,
        steps=steps,
        elapsed_s=elapsed,
        deadline_s=profile.deadline_s,
        trace=trace,
        error="physical_limit",
    )

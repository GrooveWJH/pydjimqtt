from __future__ import annotations

import time
from math import isclose
from typing import Any, Callable

from ...core import MQTTClient
from ..controller import PitchObservation, PitchSpeedPlanner, update_profile_from_observation
from ..io import send_screen_drag
from ..models import GimbalPitchTraceStep, StreamControlResult
from ..profile import GimbalPitchProfile


def within_tolerance(current: float, target: float, tolerance: float) -> bool:
    return abs(target - current) <= tolerance or isclose(
        current,
        target,
        abs_tol=tolerance + 1e-6,
    )


def run_stream_control(
    *,
    mqtt_client: MQTTClient,
    controller,
    payload_index: str,
    target: float,
    current: float,
    profile: GimbalPitchProfile,
    start_time: float,
    sleep_fn: Callable[[float], Any],
) -> StreamControlResult:
    steps = 0
    total_progress = 0.0
    last_progress_at = start_time
    last_speed = 0.0
    trace: list[GimbalPitchTraceStep] = []
    planner = PitchSpeedPlanner(profile)

    try:
        for _ in range(profile.max_control_iterations):
            before = current
            speed = planner.plan(current=current, target=target)
            if speed == 0.0:
                break
            command_started_at = time.monotonic()
            send_screen_drag(mqtt_client, payload_index=payload_index, pitch_speed=speed)
            last_speed = speed
            sleep_fn(profile.control_interval_s)
            current = controller._read_stream_pitch(previous=before, target=target, profile=profile)
            steps += 1
            progress = _progress_toward_target(before=before, current=current, target=target)
            total_progress += progress
            trace.append(_trace_step(steps, speed, before, current, progress, command_started_at))
            if progress >= profile.stall_min_progress_deg:
                last_progress_at = time.monotonic()
            profile = update_profile_from_observation(
                profile,
                PitchObservation(
                    speed=speed,
                    duration=max(profile.control_interval_s, 0.001),
                    actual_delta=current - before,
                ),
            )
            planner = PitchSpeedPlanner(profile)
            if _should_stop(current, target, profile, total_progress, last_progress_at):
                break
    finally:
        if last_speed != 0.0:
            send_screen_drag(mqtt_client, payload_index=payload_index, pitch_speed=0)
            _mark_last_trace_step_stopped(trace)
    return StreamControlResult(current, profile, steps, total_progress, trace)


def _progress_toward_target(*, before: float, current: float, target: float) -> float:
    target_direction = 1.0 if target >= before else -1.0
    return max(0.0, (current - before) * target_direction)


def _trace_step(
    index: int, speed: float, before: float, current: float, progress: float, started_at: float
) -> GimbalPitchTraceStep:
    return GimbalPitchTraceStep(
        index=index,
        commanded_speed=speed,
        start_pitch=before,
        end_pitch=current,
        progress_deg=round(progress, 3),
        duration_s=round(time.monotonic() - started_at, 3),
    )


def _should_stop(
    current: float,
    target: float,
    profile: GimbalPitchProfile,
    total_progress: float,
    last_progress_at: float,
) -> bool:
    if within_tolerance(current, target, profile.settle_tolerance_deg):
        return True
    return (
        total_progress >= profile.stall_min_progress_deg
        and time.monotonic() - last_progress_at >= profile.stall_timeout_s
    )


def _mark_last_trace_step_stopped(trace: list[GimbalPitchTraceStep]) -> None:
    if not trace:
        return
    last_step = trace[-1]
    trace[-1] = GimbalPitchTraceStep(
        index=last_step.index,
        commanded_speed=last_step.commanded_speed,
        start_pitch=last_step.start_pitch,
        end_pitch=last_step.end_pitch,
        progress_deg=last_step.progress_deg,
        duration_s=last_step.duration_s,
        stopped=True,
    )

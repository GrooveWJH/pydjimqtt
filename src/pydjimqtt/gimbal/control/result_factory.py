from __future__ import annotations

import time

from ..models import GimbalPitchResult, GimbalPitchStatus, GimbalPitchTraceStep


def failure_result(
    *,
    requested: float,
    target: float,
    start_time: float,
    deadline_s: float,
    error: Exception,
    start_pitch: float | None = None,
    final_pitch: float | None = None,
    steps: int = 0,
    trace: tuple[GimbalPitchTraceStep, ...] = (),
) -> GimbalPitchResult:
    return GimbalPitchResult(
        status=GimbalPitchStatus.FAILED,
        code=type(error).__name__,
        requested_pitch=requested,
        target_pitch=target,
        start_pitch=start_pitch,
        final_pitch=final_pitch,
        steps=steps,
        elapsed_s=round(time.monotonic() - start_time, 3),
        deadline_s=deadline_s,
        trace=trace,
        error=str(error),
    )


def pitch_result(
    *,
    status: GimbalPitchStatus,
    code: str,
    requested: float,
    target: float,
    start_pitch: float | None,
    final_pitch: float | None,
    steps: int,
    elapsed_s: float,
    deadline_s: float,
    trace: list[GimbalPitchTraceStep],
    error: str | None = None,
) -> GimbalPitchResult:
    return GimbalPitchResult(
        status=status,
        code=code,
        requested_pitch=requested,
        target_pitch=target,
        start_pitch=start_pitch,
        final_pitch=final_pitch,
        steps=steps,
        elapsed_s=round(elapsed_s, 3),
        deadline_s=deadline_s,
        trace=tuple(trace),
        error=error,
    )

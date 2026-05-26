from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum
from math import ceil, isclose
from typing import Any, Callable

from ..core import MQTTClient
from .controller import PitchObservation, PitchSpeedPlanner, clamp, update_profile_from_observation
from .io import send_screen_drag
from .profile import DEFAULT_GIMBAL_PITCH_PROFILE, GimbalPitchProfile, load_gimbal_pitch_profile


class GimbalPitchStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    UNREACHABLE = "UNREACHABLE"
    FAILED = "FAILED"


_ASYNC_EXECUTOR = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="pydjimqtt-gimbal",
)


@dataclass(frozen=True)
class GimbalPitchTraceStep:
    index: int
    commanded_speed: float
    start_pitch: float
    end_pitch: float
    progress_deg: float
    duration_s: float
    stopped: bool = False


@dataclass(frozen=True)
class GimbalPitchResult:
    status: GimbalPitchStatus
    code: str
    requested_pitch: float
    target_pitch: float
    start_pitch: float | None
    final_pitch: float | None
    steps: int
    elapsed_s: float
    deadline_s: float
    trace: tuple[GimbalPitchTraceStep, ...] = ()
    error: str | None = None

    @property
    def converged(self) -> bool:
        return self.status == GimbalPitchStatus.SUCCEEDED


@dataclass(frozen=True)
class _StreamControlResult:
    current: float
    profile: GimbalPitchProfile
    steps: int
    total_progress: float
    trace: list[GimbalPitchTraceStep]


class GimbalPitchTask:
    def __init__(self, future: Future[GimbalPitchResult]) -> None:
        self._future = future

    def status(self) -> GimbalPitchStatus:
        if not self._future.done():
            return GimbalPitchStatus.RUNNING
        return self._future.result().status

    def result(self, timeout: float | None = None) -> GimbalPitchResult:
        return self._future.result(timeout=timeout)

    def done(self) -> bool:
        return self._future.done()


def _within_tolerance(current: float, target: float, tolerance: float) -> bool:
    return abs(target - current) <= tolerance or isclose(
        current,
        target,
        abs_tol=tolerance + 1e-6,
    )


class GimbalPitchController:
    def __init__(
        self,
        mqtt_client: MQTTClient,
        *,
        profile: GimbalPitchProfile | None = None,
        payload_index: str | None = None,
        sleep_fn: Callable[[float], Any] = time.sleep,
    ) -> None:
        self.mqtt = mqtt_client
        self.profile = (
            profile
            or load_gimbal_pitch_profile(mqtt_client.gateway_sn)
            or DEFAULT_GIMBAL_PITCH_PROFILE
        )
        self.payload_index = payload_index
        self.sleep_fn = sleep_fn

    def set_pitch_async(
        self,
        target_pitch: float,
        *,
        pad_to_deadline: bool | None = None,
    ) -> GimbalPitchTask:
        return GimbalPitchTask(
            _ASYNC_EXECUTOR.submit(
                _run_pitch_control,
                self.mqtt,
                float(target_pitch),
                self.profile,
                self.payload_index,
                self.sleep_fn,
                pad_to_deadline,
            )
        )

    def _payload_index(self) -> str:
        payload_index = self.payload_index or self.mqtt.get_payload_index()
        if not payload_index:
            raise TimeoutError("camera payload_index is not available from OSD")
        return str(payload_index)

    def _read_pitch(self) -> float:
        pitch, _roll, _yaw = self.mqtt.get_gimbal_attitude()
        if pitch is None:
            raise TimeoutError("gimbal pitch is not available from camera OSD")
        return float(pitch)

    def _read_stream_pitch(
        self,
        *,
        previous: float,
        target: float,
        profile: GimbalPitchProfile,
    ) -> float:
        current = previous
        wait_s = max(profile.control_interval_s, 0.02)
        deadline = time.monotonic() + max(
            profile.observation_window_s,
            profile.control_interval_s,
        )
        max_reads = max(
            1,
            profile.confirm_reads + ceil(profile.observation_window_s / wait_s),
        )
        for read_index in range(max_reads):
            current = self._read_pitch()
            if _within_tolerance(current, target, profile.settle_tolerance_deg):
                return current
            if abs(current - previous) >= profile.stall_min_progress_deg:
                return current
            if time.monotonic() >= deadline:
                return current
            if read_index < max_reads - 1:
                self.sleep_fn(wait_s)
        return current


def _failure_result(
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


def _pitch_result(
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


def _progress_toward_target(*, before: float, current: float, target: float) -> float:
    target_direction = 1.0 if target >= before else -1.0
    return max(0.0, (current - before) * target_direction)


def _run_stream_control(
    *,
    mqtt_client: MQTTClient,
    controller: GimbalPitchController,
    payload_index: str,
    target: float,
    current: float,
    profile: GimbalPitchProfile,
    start_time: float,
    sleep_fn: Callable[[float], Any],
) -> _StreamControlResult:
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
            current = controller._read_stream_pitch(
                previous=before,
                target=target,
                profile=profile,
            )
            steps += 1

            delta = current - before
            progress = _progress_toward_target(
                before=before,
                current=current,
                target=target,
            )
            total_progress += progress
            trace.append(
                GimbalPitchTraceStep(
                    index=steps,
                    commanded_speed=speed,
                    start_pitch=before,
                    end_pitch=current,
                    progress_deg=round(progress, 3),
                    duration_s=round(time.monotonic() - command_started_at, 3),
                )
            )
            if progress >= profile.stall_min_progress_deg:
                last_progress_at = time.monotonic()

            profile = update_profile_from_observation(
                profile,
                PitchObservation(
                    speed=speed,
                    duration=max(profile.control_interval_s, 0.001),
                    actual_delta=delta,
                ),
            )
            planner = PitchSpeedPlanner(profile)

            if _within_tolerance(current, target, profile.settle_tolerance_deg):
                break
            if (
                total_progress >= profile.stall_min_progress_deg
                and time.monotonic() - last_progress_at >= profile.stall_timeout_s
            ):
                break
    finally:
        if last_speed != 0.0:
            send_screen_drag(mqtt_client, payload_index=payload_index, pitch_speed=0)
            _mark_last_trace_step_stopped(trace)

    return _StreamControlResult(
        current=current,
        profile=profile,
        steps=steps,
        total_progress=total_progress,
        trace=trace,
    )


def _apply_deadline_padding(
    *,
    profile: GimbalPitchProfile,
    pad_to_deadline: bool | None,
    start_time: float,
    sleep_fn: Callable[[float], Any],
) -> float:
    elapsed = time.monotonic() - start_time
    should_pad = profile.pad_to_deadline if pad_to_deadline is None else pad_to_deadline
    if should_pad and elapsed < profile.deadline_s:
        sleep_fn(profile.deadline_s - elapsed)
        return time.monotonic() - start_time
    return elapsed


def _confirm_final_pitch(
    *,
    controller: GimbalPitchController,
    current: float,
    target: float,
    profile: GimbalPitchProfile,
    start_time: float,
    sleep_fn: Callable[[float], Any],
) -> tuple[float, float]:
    elapsed = time.monotonic() - start_time
    for _ in range(max(1, profile.confirm_reads)):
        if _within_tolerance(current, target, profile.settle_tolerance_deg):
            break
        sleep_fn(profile.settle_seconds)
        current = controller._read_pitch()
        elapsed = time.monotonic() - start_time
    return current, elapsed


def _run_pitch_control(
    mqtt_client: MQTTClient,
    requested: float,
    profile: GimbalPitchProfile,
    payload_index: str | None,
    sleep_fn: Callable[[float], Any],
    pad_to_deadline: bool | None,
) -> GimbalPitchResult:
    start_time = time.monotonic()
    target = clamp(requested, profile.pitch_min, profile.pitch_max)
    controller = GimbalPitchController(
        mqtt_client,
        profile=profile,
        payload_index=payload_index,
        sleep_fn=sleep_fn,
    )

    start_pitch: float | None = None
    current: float | None = None
    steps = 0
    total_progress = 0.0
    trace: list[GimbalPitchTraceStep] = []

    try:
        if mqtt_client.client is None:
            raise RuntimeError("MQTT client is not connected")

        start_pitch = controller._read_pitch()
        current = start_pitch

        payload = controller._payload_index()
        stream_result = _run_stream_control(
            mqtt_client=mqtt_client,
            controller=controller,
            payload_index=payload,
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
        elapsed = _apply_deadline_padding(
            profile=profile,
            pad_to_deadline=pad_to_deadline,
            start_time=start_time,
            sleep_fn=sleep_fn,
        )

        if current is None:
            raise RuntimeError("gimbal pitch read did not produce a value")

        current, elapsed = _confirm_final_pitch(
            controller=controller,
            current=current,
            target=target,
            profile=profile,
            start_time=start_time,
            sleep_fn=sleep_fn,
        )

        if _within_tolerance(current, target, profile.settle_tolerance_deg):
            return _pitch_result(
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
            return _pitch_result(
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

        return _pitch_result(
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
    except Exception as exc:
        return _failure_result(
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


def set_gimbal_pitch_async(
    mqtt_client: MQTTClient,
    target_pitch: float,
    *,
    profile: GimbalPitchProfile | None = None,
    payload_index: str | None = None,
    pad_to_deadline: bool | None = None,
    sleep_fn: Callable[[float], Any] = time.sleep,
) -> GimbalPitchTask:
    """
    Start a background gimbal pitch move and return a queryable task immediately.

    The target pitch range is -90.0 <= target_pitch <= 90.0 degrees. The target
    is treated as operator intent; physical aircraft limits are reported through
    a final UNREACHABLE result instead of being silently clamped to a model.
    When profile is None, a saved gateway-specific calibration profile is loaded
    before falling back to DEFAULT_GIMBAL_PITCH_PROFILE.
    """
    return GimbalPitchController(
        mqtt_client,
        profile=profile,
        payload_index=payload_index,
        sleep_fn=sleep_fn,
    ).set_pitch_async(target_pitch, pad_to_deadline=pad_to_deadline)

from __future__ import annotations

import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Any

from ..core import MQTTClient
from .controller import (
    PitchObservation,
    PitchPulsePlanner,
    clamp,
    update_profile_from_observation,
)
from .io import send_screen_drag_pulse
from .profile import DEFAULT_GIMBAL_PITCH_PROFILE, GimbalPitchProfile

_ASYNC_EXECUTOR = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="pydjimqtt-gimbal",
)


@dataclass(frozen=True)
class GimbalPitchResult:
    requested_pitch: float
    target_pitch: float
    start_pitch: float
    final_pitch: float
    converged: bool
    steps: int
    elapsed_s: float
    deadline_s: float
    clamped: bool


class GimbalPitchController:
    def __init__(
        self,
        mqtt_client: MQTTClient,
        *,
        profile: GimbalPitchProfile = DEFAULT_GIMBAL_PITCH_PROFILE,
        payload_index: str | None = None,
        sleep_fn: Callable[[float], Any] = time.sleep,
    ) -> None:
        self.mqtt = mqtt_client
        self.profile = profile
        self.payload_index = payload_index
        self.sleep_fn = sleep_fn

    def set_pitch(
        self,
        target_pitch: float,
        *,
        pad_to_deadline: bool | None = None,
    ) -> GimbalPitchResult:
        if self.mqtt.client is None:
            raise RuntimeError("MQTT client is not connected")

        requested = float(target_pitch)
        target = clamp(requested, self.profile.pitch_min, self.profile.pitch_max)
        start_time = time.monotonic()
        start_pitch = self._read_pitch()
        current = start_pitch
        steps = 0

        should_pad = self.profile.pad_to_deadline if pad_to_deadline is None else pad_to_deadline

        for _ in range(self.profile.max_pulses):
            planner = PitchPulsePlanner(self.profile)
            command = planner.plan(current=current, target=target)
            if command is None:
                break

            before = current
            send_screen_drag_pulse(
                self.mqtt,
                payload_index=self._payload_index(),
                pitch_speed=command.speed,
                duration=command.duration,
                sleep_fn=self.sleep_fn,
            )
            self.sleep_fn(self.profile.settle_seconds)
            current = self._read_pitch()
            steps += 1
            self.profile = update_profile_from_observation(
                self.profile,
                PitchObservation(
                    speed=command.speed,
                    duration=command.duration,
                    actual_delta=current - before,
                ),
            )
            if abs(target - current) <= self.profile.settle_tolerance_deg:
                break

        elapsed = time.monotonic() - start_time
        if should_pad and elapsed < self.profile.target_total_time_s:
            self.sleep_fn(self.profile.target_total_time_s - elapsed)
            elapsed = time.monotonic() - start_time

        return GimbalPitchResult(
            requested_pitch=requested,
            target_pitch=target,
            start_pitch=start_pitch,
            final_pitch=current,
            converged=abs(target - current) <= self.profile.settle_tolerance_deg,
            steps=steps,
            elapsed_s=round(elapsed, 3),
            deadline_s=self.profile.target_total_time_s,
            clamped=requested != target,
        )

    def set_pitch_async(
        self,
        target_pitch: float,
        *,
        pad_to_deadline: bool | None = None,
    ) -> Future[GimbalPitchResult]:
        return _ASYNC_EXECUTOR.submit(
            self.set_pitch,
            target_pitch,
            pad_to_deadline=pad_to_deadline,
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


def set_gimbal_pitch(
    mqtt_client: MQTTClient,
    target_pitch: float,
    *,
    profile: GimbalPitchProfile = DEFAULT_GIMBAL_PITCH_PROFILE,
    payload_index: str | None = None,
    pad_to_deadline: bool | None = None,
    sleep_fn: Callable[[float], Any] = time.sleep,
) -> GimbalPitchResult:
    """
    Move the gimbal to a requested pitch angle with the accepted fixed-deadline profile.

    This function is blocking. Use set_gimbal_pitch_async() when the caller must
    keep other control code running while the gimbal closes on the target.

    Pitch target safe range: -90.0 <= target_pitch <= 35.0 degrees.
    Out-of-range targets are clamped to this range before any pulse is sent.
    """
    return GimbalPitchController(
        mqtt_client,
        profile=profile,
        payload_index=payload_index,
        sleep_fn=sleep_fn,
    ).set_pitch(target_pitch, pad_to_deadline=pad_to_deadline)


def set_gimbal_pitch_async(
    mqtt_client: MQTTClient,
    target_pitch: float,
    *,
    profile: GimbalPitchProfile = DEFAULT_GIMBAL_PITCH_PROFILE,
    payload_index: str | None = None,
    pad_to_deadline: bool | None = None,
    sleep_fn: Callable[[float], Any] = time.sleep,
) -> Future[GimbalPitchResult]:
    """
    Start a background gimbal pitch move and return a Future immediately.

    Pitch target safe range: -90.0 <= target_pitch <= 35.0 degrees.
    Out-of-range targets are clamped to this range before any pulse is sent.
    Exceptions raised by the controller are delivered through future.result().
    """
    controller = GimbalPitchController(
        mqtt_client,
        profile=profile,
        payload_index=payload_index,
        sleep_fn=sleep_fn,
    )
    return controller.set_pitch_async(target_pitch, pad_to_deadline=pad_to_deadline)

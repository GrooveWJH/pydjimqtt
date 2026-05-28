from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from math import ceil
from typing import Any, Callable

from ..core import MQTTClient
from .models import GimbalPitchResult, GimbalPitchStatus, GimbalPitchTraceStep
from .control.pitch_control import run_pitch_control
from .profile import DEFAULT_GIMBAL_PITCH_PROFILE, GimbalPitchProfile, load_gimbal_pitch_profile
from .control.stream_control import within_tolerance
from .task import GimbalPitchTask

_ASYNC_EXECUTOR = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="pydjimqtt-gimbal",
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
                run_pitch_control,
                self.mqtt,
                float(target_pitch),
                self.profile,
                self.payload_index,
                self.sleep_fn,
                pad_to_deadline,
                GimbalPitchController,
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
            if within_tolerance(current, target, profile.settle_tolerance_deg):
                return current
            if abs(current - previous) >= profile.stall_min_progress_deg:
                return current
            if time.monotonic() >= deadline:
                return current
            if read_index < max_reads - 1:
                self.sleep_fn(wait_s)
        return current


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
    """
    return GimbalPitchController(
        mqtt_client,
        profile=profile,
        payload_index=payload_index,
        sleep_fn=sleep_fn,
    ).set_pitch_async(target_pitch, pad_to_deadline=pad_to_deadline)


__all__ = [
    "GimbalPitchController",
    "GimbalPitchResult",
    "GimbalPitchStatus",
    "GimbalPitchTask",
    "GimbalPitchTraceStep",
    "set_gimbal_pitch_async",
]

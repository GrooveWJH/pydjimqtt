from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .profile import GimbalPitchProfile


class GimbalPitchStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    UNREACHABLE = "UNREACHABLE"
    FAILED = "FAILED"


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
class StreamControlResult:
    current: float
    profile: GimbalPitchProfile
    steps: int
    total_progress: float
    trace: list[GimbalPitchTraceStep]

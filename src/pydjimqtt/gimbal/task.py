from __future__ import annotations

from concurrent.futures import Future

from .models import GimbalPitchResult, GimbalPitchStatus


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

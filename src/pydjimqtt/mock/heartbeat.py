from __future__ import annotations

import threading


class MockHeartbeatThread(threading.Thread):
    """模拟的心跳线程。"""

    def __init__(self):
        super().__init__(daemon=True)
        self.stop_flag = threading.Event()
        self._mock_alive = True
        self._started = False

    def is_alive(self) -> bool:
        return self._mock_alive and not self.stop_flag.is_set()

    def run(self):
        pass

    def start(self):
        self._started = True

    def join(self, timeout=None):
        pass

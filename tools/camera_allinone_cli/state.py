"""Shared runtime state for the multi-drone camera controller."""

import threading
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from typing import Any

uav_states: dict[str, dict[str, Any]] = {}
stop_flag = False
executor = ThreadPoolExecutor(max_workers=10)
lookdown_lock = False
aim_down_lock = False
print_lock = threading.Lock()


def log(msg: str) -> None:
    import sys
    import time

    with print_lock:
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}")
        sys.stdout.flush()


def parallel_run(name: str, action: Callable[[str, dict[str, Any]], None]) -> None:
    log(f">>> {name}")

    def run_single(item: tuple[str, dict[str, Any]]) -> None:
        callsign, drone_state = item
        try:
            action(callsign, drone_state)
            log(f"  ✓ {callsign}")
        except Exception as exc:
            log(f"  ✗ {callsign}: {exc}")

    list(executor.map(run_single, uav_states.items()))

from __future__ import annotations

import time
from typing import Any

TERMINAL_STATUSES = {"wayline_ok", "wayline_failed", "wayline_cancel"}


def wait_for_flyto_event(
    client,
    expected_fly_to_id: str,
    timeout: float = 120.0,
    poll_interval: float = 1.0,
) -> dict[str, Any]:
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError(f"等待 fly_to_id={expected_fly_to_id} 的事件超时（{timeout}秒）")

        progress = client.get_flyto_progress()
        if (
            progress.get("fly_to_id") == expected_fly_to_id
            and progress.get("status") in TERMINAL_STATUSES
        ):
            return progress
        time.sleep(poll_interval)

from __future__ import annotations

import time
from typing import Any, Optional

MODE_NAMES = {
    0: "待机",
    1: "起飞准备",
    2: "起飞准备完毕",
    3: "摇杆控制",
    4: "自动起飞",
    5: "航线飞行",
    6: "全景拍照",
    7: "智能跟随",
    8: "ADS-B 躲避",
    9: "自动返航",
    10: "自动降落",
    11: "强制降落",
    12: "三桨叶降落",
    13: "升级中",
    14: "未连接",
    15: "APAS",
    16: "虚拟摇杆状态",
    17: "指令飞行",
}


def get_connection_diagnostics(client) -> dict[str, Any]:
    connected = False
    if client.client is not None:
        try:
            connected = bool(client.client.is_connected())
        except Exception:
            connected = False
    return {
        "connected": connected,
        "last_disconnect_rc": client._last_disconnect_rc,
        "last_disconnect_at": client._last_disconnect_at,
    }


def get_hsi_data(client) -> dict[str, Any]:
    with client.lock:
        snapshot = client.hsi_data.copy()
        around = snapshot.get("around_distances")
        snapshot["around_distances"] = list(around) if isinstance(around, list) else []
        return snapshot


def get_around_distances(client) -> list[int]:
    with client.lock:
        around = client.hsi_data.get("around_distances")
        if not isinstance(around, list):
            return []
        return [int(value) for value in around]


def get_aircraft_sn(client) -> Optional[str]:
    with client.lock:
        if client.topo_data and "sub_devices" in client.topo_data:
            sub_devices = client.topo_data.get("sub_devices", [])
            if sub_devices and len(sub_devices) > 0:
                return sub_devices[0].get("sn")
        return None


def wait_for_gimbal_attitude(
    client, timeout: float, poll_interval: float
) -> tuple[float, float, float]:
    deadline = time.monotonic() + max(0.0, timeout)
    interval = max(0.01, poll_interval)
    while time.monotonic() <= deadline:
        pitch, roll, yaw = client.get_gimbal_attitude()
        if pitch is not None and roll is not None and yaw is not None:
            return float(pitch), float(roll), float(yaw)
        time.sleep(interval)
    raise TimeoutError(f"gimbal attitude is not available within {timeout:.1f}s")


def get_osd_frequency(client) -> float:
    with client.lock:
        if len(client._osd_timestamps) < 2:
            return 0.0
        time_span = client._osd_timestamps[-1] - client._osd_timestamps[0]
        if time_span == 0:
            return 0.0
        return (len(client._osd_timestamps) - 1) / time_span


def is_online(client, timeout: float = 2.0) -> bool:
    with client.lock:
        if client._last_osd_time == 0:
            return False
        return (time.time() - client._last_osd_time) < timeout

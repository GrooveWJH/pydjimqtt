"""Background control loops."""

import threading
import time

from pydjimqtt import reset_gimbal

from . import state
from .actions import aim_down_once


def aim_down_loop() -> None:
    while state.aim_down_lock and not state.stop_flag:
        for drone_state in state.uav_states.values():
            try:
                aim_down_once(drone_state)
            except Exception:
                pass
        time.sleep(0.1)


def toggle_aim_down() -> None:
    state.aim_down_lock = not state.aim_down_lock
    if state.aim_down_lock:
        state.log(">>> AIM 正下方锁定 [ON] (10Hz)")
        threading.Thread(target=aim_down_loop, daemon=True).start()
    else:
        state.log(">>> AIM 正下方锁定 [OFF]")


def lookdown_loop() -> None:
    while state.lookdown_lock and not state.stop_flag:
        for drone_state in state.uav_states.values():
            try:
                reset_gimbal(
                    drone_state["mqtt"], drone_state["mqtt"].get_payload_index() or "88-0-0", 1
                )
            except Exception:
                pass
        time.sleep(0.02)


def toggle_lookdown() -> None:
    state.lookdown_lock = not state.lookdown_lock
    if state.lookdown_lock:
        state.log(">>> 低头锁定 [ON] (50Hz)")
        threading.Thread(target=lookdown_loop, daemon=True).start()
    else:
        state.log(">>> 低头锁定 [OFF]")


def status_loop() -> None:
    while not state.stop_flag:
        for callsign, drone_state in state.uav_states.items():
            if not drone_state["mqtt"].is_online(timeout=3.0):
                state.log(f"⚠ {callsign}: 连接断开")
        time.sleep(5.0)

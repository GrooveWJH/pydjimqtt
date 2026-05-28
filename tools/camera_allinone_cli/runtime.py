"""Main runtime orchestration for the multi-drone camera controller."""

import threading

from pydjimqtt import setup_multiple_drc_connections, stop_heartbeat

from . import state
from .config import MQTT_CONFIG, UAV_CONFIGS
from .keyboard import keyboard_loop
from .loops import status_loop


def main() -> None:
    state.stop_flag = False

    print("\n=== 多无人机相机同步控制 ===\n")
    print("正在连接...")

    connections = setup_multiple_drc_connections(
        UAV_CONFIGS, MQTT_CONFIG, osd_frequency=1, hsi_frequency=1, skip_drc_setup=True
    )
    print(f"✓ {len(connections)} 架已连接\n")

    state.uav_states.clear()
    for (mqtt, caller, heartbeat), config in zip(connections, UAV_CONFIGS):
        state.uav_states[config["callsign"]] = {
            "mqtt": mqtt,
            "caller": caller,
            "heartbeat": heartbeat,
            "config": config,
        }

    print("控制: ↑回中 ↓向下 p看地面 z放大 x缩小 l低头锁定 w切换镜头 a AIM锁定 q/Ctrl+C退出\n")

    try:
        threading.Thread(target=status_loop, daemon=True).start()
        keyboard_loop()
    except KeyboardInterrupt:
        state.stop_flag = True
    finally:
        _disconnect_all()


def _disconnect_all() -> None:
    print("\n断开连接...")
    for callsign, drone_state in state.uav_states.items():
        try:
            stop_heartbeat(drone_state["heartbeat"])
            drone_state["mqtt"].disconnect()
            print(f"✓ {callsign}")
        except Exception as exc:
            print(f"⚠ {callsign}: {exc}")
    state.executor.shutdown(wait=False)
    print("✓ 完成\n")

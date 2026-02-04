#!/usr/bin/env python3
"""
多无人机相机同步控制工具

键盘: ↑回中 ↓向下 p看地面 z放大 x缩小 l低头锁定 w切换镜头 a AIM锁定 q/Ctrl+C退出
"""

import sys
import os

# Add parent directory (pythonSDK/) to path to import pydjimqtt module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import tty
import termios
import threading
from concurrent.futures import ThreadPoolExecutor

from pydjimqtt import (
    setup_multiple_drc_connections,
    stop_heartbeat,
    reset_gimbal,
    camera_look_at,
    set_camera_zoom,
    camera_aim,
    change_live_lens,
)

# ========== 配置 ==========

MQTT_CONFIG = {
    "host": "grve.me",
    "port": 1883,
    "username": "dji",
    "password": "lab605605",
}

UAV_CONFIGS = [
    {
        "name": "Drone001",
        "sn": "9N9CN2J0012CXY",
        "callsign": "Alpha",
        "camera_type": "zoom",
        "zoom": {"current": 7, "step": 1, "min": 1, "max": 112},
    },
    {
        "name": "Drone002",
        "sn": "9N9CN8400164WH",
        "callsign": "Bravo",
        "camera_type": "zoom",
        "zoom": {"current": 5, "step": 1, "min": 1, "max": 112},
    },
    {
        "name": "Drone003",
        "sn": "9N9CN180011TJN",
        "callsign": "Charlie",
        "camera_type": "zoom",
        "zoom": {"current": 10, "step": 1, "min": 1, "max": 112},
    },
]

# ========== 全局状态 ==========

uav_states = {}
stop_flag = False
executor = ThreadPoolExecutor(max_workers=10)
lookdown_lock = False
aim_down_lock = False
print_lock = threading.Lock()

# ========== 工具函数 ==========


def log(msg):
    """线程安全打印"""
    with print_lock:
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}")
        sys.stdout.flush()


# ========== 并行控制 ==========


def parallel_run(name, action):
    """并行执行所有无人机的控制指令"""
    log(f">>> {name}")

    def run_single(item):
        cs, state = item
        try:
            action(cs, state)
            log(f"  ✓ {cs}")
        except Exception as e:
            log(f"  ✗ {cs}: {e}")

    list(executor.map(run_single, uav_states.items()))


# ========== 控制函数 ==========


def gimbal_center():
    def action(cs, s):
        reset_gimbal(s["mqtt"], s["mqtt"].get_payload_index() or "88-0-0", 0)

    parallel_run("云台回中", action)


def gimbal_down():
    def action(cs, s):
        reset_gimbal(s["mqtt"], s["mqtt"].get_payload_index() or "88-0-0", 1)

    parallel_run("云台向下", action)


def lookat_ground():
    def action(cs, s):
        lat, lon, h = s["mqtt"].get_position()
        if not lat:
            raise Exception("无GPS")
        target = (h or 0) - 100
        camera_look_at(
            s["mqtt"],
            s["mqtt"].get_payload_index() or "88-0-0",
            lat,
            lon,
            target,
            False,
        )

    parallel_run("看地面", action)


def zoom_in():
    def action(cs, s):
        # 只在变焦模式下有效
        if s["config"]["camera_type"] != "zoom":
            log(f"  - {cs}: 广角模式不支持变焦")
            return
        z = s["config"]["zoom"]
        z["current"] = min(z["current"] + z["step"], z["max"])
        set_camera_zoom(
            s["mqtt"], s["mqtt"].get_payload_index() or "88-0-0", z["current"], "zoom"
        )
        log(f"  {cs}: {z['current']}x")

    parallel_run("放大", action)


def zoom_out():
    def action(cs, s):
        # 只在变焦模式下有效
        if s["config"]["camera_type"] != "zoom":
            log(f"  - {cs}: 广角模式不支持变焦")
            return
        z = s["config"]["zoom"]
        z["current"] = max(z["current"] - z["step"], z["min"])
        set_camera_zoom(
            s["mqtt"], s["mqtt"].get_payload_index() or "88-0-0", z["current"], "zoom"
        )
        log(f"  {cs}: {z['current']}x")

    parallel_run("缩小", action)


def toggle_camera_type():
    """切换相机类型（变焦 ↔ 广角）- 照搬 live.py 方案"""

    def action(cs, s):
        current_type = s["config"]["camera_type"]
        new_type = "wide" if current_type == "zoom" else "zoom"
        type_name = "广角" if new_type == "wide" else "变焦"

        # 构建 video_id（格式：sn/payload_index/video_index）
        sn = s["mqtt"].gateway_sn
        payload_index = s["mqtt"].get_payload_index() or "88-0-0"
        video_index = "normal-0"  # 默认视频流索引
        video_id = f"{sn}/{payload_index}/{video_index}"

        # 调用 change_live_lens 服务（参考 live.py:300）
        change_live_lens(s["caller"], video_id, new_type)

        # 更新本地状态
        s["config"]["camera_type"] = new_type
        log(f"  {cs}: {type_name}")

    parallel_run("切换镜头", action)


# ========== AIM 正下方锁定 ==========


def aim_down_loop():
    """10Hz频率持续发送 AIM 正下方指令"""
    while aim_down_lock and not stop_flag:
        for cs, s in uav_states.items():
            try:
                camera_type = s["config"]["camera_type"]
                camera_aim(
                    s["mqtt"],
                    s["mqtt"].get_payload_index() or "88-0-0",
                    x=0.5,
                    y=1.0,
                    camera_type=camera_type,
                    locked=False,
                )
            except Exception:
                pass
        time.sleep(0.1)  # 10Hz


def toggle_aim_down():
    """切换 AIM 正下方锁定状态"""
    global aim_down_lock
    aim_down_lock = not aim_down_lock
    if aim_down_lock:
        log(">>> AIM 正下方锁定 [ON] (10Hz)")
        threading.Thread(target=aim_down_loop, daemon=True).start()
    else:
        log(">>> AIM 正下方锁定 [OFF]")


# ========== 低头锁定 ==========


def lookdown_loop():
    """50Hz频率持续发送云台向下指令"""
    while lookdown_lock and not stop_flag:
        for cs, s in uav_states.items():
            try:
                reset_gimbal(s["mqtt"], s["mqtt"].get_payload_index() or "88-0-0", 1)
            except Exception:
                pass
        time.sleep(0.02)  # 50Hz


def toggle_lookdown():
    """切换低头锁定状态"""
    global lookdown_lock
    lookdown_lock = not lookdown_lock
    if lookdown_lock:
        log(">>> 低头锁定 [ON] (50Hz)")
        threading.Thread(target=lookdown_loop, daemon=True).start()
    else:
        log(">>> 低头锁定 [OFF]")


# ========== 状态监控 ==========


def status_loop():
    """定期状态检查（仅警告）"""
    while not stop_flag:
        for cs, s in uav_states.items():
            # 只在异常时打印
            if not s["mqtt"].is_online(timeout=3.0):
                log(f"⚠ {cs}: 连接断开")

        time.sleep(5.0)  # 5秒检查一次


# ========== 键盘输入 ==========


def getch():
    """读取单个字符"""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def keyboard_loop():
    """键盘监听循环"""
    global stop_flag
    KEY_MAP = {
        "\x1b[A": gimbal_center,
        "\x1b[B": gimbal_down,
        "p": lookat_ground,
        "z": zoom_in,
        "x": zoom_out,
        "l": toggle_lookdown,
        "w": toggle_camera_type,
        "a": toggle_aim_down,  # ← 更新为 toggle
    }

    while not stop_flag:
        try:
            ch = getch()
            if ch == "\x1b":
                ch2 = getch()
                if ch2 == "[":
                    ch = "\x1b[" + getch()
            if ch == "q" or ch == "\x03":  # q 或 Ctrl+C
                log(">>> 退出")
                stop_flag = True
                break
            elif ch in KEY_MAP:
                KEY_MAP[ch]()
        except Exception:
            pass


# ========== 主程序 ==========


def main():
    global stop_flag

    print("\n=== 多无人机相机同步控制 ===\n")
    print("正在连接...")

    connections = setup_multiple_drc_connections(
        UAV_CONFIGS, MQTT_CONFIG, osd_frequency=1, hsi_frequency=1, skip_drc_setup=True
    )
    print(f"✓ {len(connections)} 架已连接\n")

    for (mqtt, caller, heartbeat), config in zip(connections, UAV_CONFIGS):
        uav_states[config["callsign"]] = {
            "mqtt": mqtt,
            "caller": caller,
            "heartbeat": heartbeat,
            "config": config,
        }

    print(
        "控制: ↑回中 ↓向下 p看地面 z放大 x缩小 l低头锁定 w切换镜头 a AIM锁定 q/Ctrl+C退出\n"
    )

    try:
        # 启动状态监控
        threading.Thread(target=status_loop, daemon=True).start()

        # 键盘监听（主线程）
        keyboard_loop()

    except KeyboardInterrupt:
        stop_flag = True

    finally:
        print("\n断开连接...")
        for cs, s in uav_states.items():
            try:
                stop_heartbeat(s["heartbeat"])
                s["mqtt"].disconnect()
                print(f"✓ {cs}")
            except Exception as e:
                print(f"⚠ {cs}: {e}")
        executor.shutdown(wait=False)
        print("✓ 完成\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"异常: {e}")
        import traceback

        traceback.print_exc()

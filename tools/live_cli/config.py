from __future__ import annotations

import threading

MQTT_CONFIG = {
    "host": "81.70.222.38",
    "port": 1883,
    "username": "dji",
    "password": "lab605605",
}

UAV_CONFIGS = [
    {
        "name": "Drone001",
        "sn": "9N9CN2J0012CXY",
        "user_id": "pilot_1",
        "callsign": "Alpha",
        "rtmp_stream_key": "Drone001",
        "video_index": "normal-0",
        "video_quality": 4,
        "zoom": {"enabled": True, "initial": 1, "step": 1},
    },
    {
        "name": "Drone002",
        "sn": "9N9CN8400164WH",
        "user_id": "pilot_2",
        "callsign": "Bravo",
        "rtmp_stream_key": "Drone002",
        "video_index": "normal-0",
        "video_quality": 4,
        "zoom": {"enabled": True, "initial": 1, "step": 1},
    },
    {
        "name": "Drone003",
        "sn": "9N9CN180011TJN",
        "user_id": "pilot_3",
        "callsign": "Charlie",
        "rtmp_stream_key": "Drone003",
        "video_index": "normal-0",
        "video_quality": 4,
        "zoom": {"enabled": True, "initial": 1, "step": 1},
    },
]

RTMP_BASE_URL = "rtmp://81.70.222.38:1935/live/"
OSD_FREQUENCY = 1
HSI_FREQUENCY = 1
STOP_LIVE_ON_EXIT = True
QUALITY_NAMES = {0: "自适应", 1: "流畅", 2: "标清", 3: "高清", 4: "超清"}

connections = {}
live_states = {}
stop_event = threading.Event()

"""Default multi-drone camera control configuration."""

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

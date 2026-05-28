"""Default MQTT sniffer configuration."""

MQTT_CONFIG = {
    "host": "81.70.222.38",
    "port": 1883,
    "username": "dji",
    "password": "lab605605",
}
GATEWAY_SN = "9N9CN2J0012CXY"
USER_ID, USER_CALLSIGN = "groove", "吴建豪"

OSD_FREQUENCY, HSI_FREQUENCY = 1, 1
HEARTBEAT_INTERVAL = 1.0

ENABLE_DRC_MODE = True
SNIFF_TOPICS = [
    f"sys/product/{GATEWAY_SN}/status",
    f"thing/product/{GATEWAY_SN}/events_reply",
    f"thing/product/{GATEWAY_SN}/drc/up",
    f"sys/product/{GATEWAY_SN}/network/probe",
]
OUTPUT_BASE_DIR = "data/sniffed_data"

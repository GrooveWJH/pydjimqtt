#!/usr/bin/env python3
"""DJI MQTT sniffer compatibility entrypoint."""

import sys
from pathlib import Path

script_dir = Path(__file__).resolve().parent
parent_dir = script_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

try:
    from .sniffer import TopicSniffer
    from .sniffer.cli import main
    from .sniffer.config import (
        ENABLE_DRC_MODE,
        GATEWAY_SN,
        HEARTBEAT_INTERVAL,
        HSI_FREQUENCY,
        MQTT_CONFIG,
        OSD_FREQUENCY,
        OUTPUT_BASE_DIR,
        SNIFF_TOPICS,
        USER_CALLSIGN,
        USER_ID,
    )
except ImportError:
    from sniffer import TopicSniffer
    from sniffer.cli import main
    from sniffer.config import (
        ENABLE_DRC_MODE,
        GATEWAY_SN,
        HEARTBEAT_INTERVAL,
        HSI_FREQUENCY,
        MQTT_CONFIG,
        OSD_FREQUENCY,
        OUTPUT_BASE_DIR,
        SNIFF_TOPICS,
        USER_CALLSIGN,
        USER_ID,
    )

__all__ = [
    "ENABLE_DRC_MODE",
    "GATEWAY_SN",
    "HEARTBEAT_INTERVAL",
    "HSI_FREQUENCY",
    "MQTT_CONFIG",
    "OSD_FREQUENCY",
    "OUTPUT_BASE_DIR",
    "SNIFF_TOPICS",
    "TopicSniffer",
    "USER_CALLSIGN",
    "USER_ID",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())

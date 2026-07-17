from __future__ import annotations

from concurrent.futures import Future
from typing import Any


def initialize_client_state(client, mqtt_client_type) -> None:
    client.client: mqtt_client_type | None = None
    client.pending_requests: dict[str, Future] = {}
    client.osd_data: dict[str, Any] = {
        "latitude": None,
        "longitude": None,
        "height": None,
        "attitude_head": None,
        "horizontal_speed": None,
        "speed_x": None,
        "speed_y": None,
        "speed_z": None,
        "down_distance": None,
        "down_enable": None,
        "down_work": None,
        "battery_percent": None,
    }
    client.drone_state: dict[str, Any] = {
        "mode_code": None,
        "rth_altitude": None,
        "distance_limit": None,
        "height_limit": None,
        "is_in_fixed_speed": None,
        "night_lights_state": None,
    }
    client.topo_data = None
    client.camera_osd: dict[str, Any] = {
        "payload_index": None,
        "gimbal_pitch": None,
        "gimbal_roll": None,
        "gimbal_yaw": None,
        "screen_split_enable": None,
        "ir_zoom_factor": None,
        "zoom_factor": None,
    }
    client.hsi_data: dict[str, Any] = {
        "around_distances": [],
        "up_distance": None,
        "down_distance": None,
        "up_enable": None,
        "up_work": None,
        "down_enable": None,
        "down_work": None,
        "left_enable": None,
        "left_work": None,
        "right_enable": None,
        "right_work": None,
        "front_enable": None,
        "front_work": None,
        "back_enable": None,
        "back_work": None,
        "vertical_enable": None,
        "vertical_work": None,
        "horizontal_enable": None,
        "horizontal_work": None,
        "timestamp": None,
        "seq": None,
    }
    client.takeoff_height = None
    client.flyto_progress: dict[str, Any] = {
        "fly_to_id": None,
        "status": None,
        "result": None,
        "way_point_index": None,
        "remaining_distance": None,
        "remaining_time": None,
        "planned_path_points": None,
    }
    client.osd_callbacks = []
    client._osd_timestamps = []
    client._last_osd_time = 0.0
    client._freq_window = 2.0
    client._last_disconnect_rc = None
    client._last_disconnect_at = None
    client._mqtt_disconnect_count = 0
    client._last_battery_msg_monotonic = None
    client._last_osd_msg_monotonic = None
    client._osd_message_count = 0
    client._osd_arrival_intervals = []
    client._drc_message_count = 0
    client._last_drc_msg_monotonic = None
    client._last_drc_seq = None
    client._drc_sequence_discontinuities = 0
    client._drc_sequence_missing_total = 0
    client._last_hsi_msg_monotonic = None

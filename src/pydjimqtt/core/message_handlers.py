from __future__ import annotations

import json
import time
from typing import Any, Optional


def handle_message(client, msg, console) -> None:
    payload = json.loads(msg.payload.decode())
    method = payload.get("method")
    if method == "osd_info_push":
        _handle_osd(client, payload)
        return
    if method == "hsi_info_push":
        _handle_hsi(client, payload)
        return
    if method == "drc_batteries_info_push":
        _handle_battery(client, payload)
        return
    if method == "drc_drone_state_push":
        _handle_drone_state(client, payload)
        return
    if method == "update_topo":
        with client.lock:
            client.topo_data = payload.get("data", {})
        return
    if method == "drc_camera_osd_info_push":
        _handle_camera_osd(client, payload)
        return
    if method == "fly_to_point_progress":
        _handle_flyto_progress(client, payload)
        return
    _handle_service_response(client, payload, console)


def _to_optional_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _handle_osd(client, payload: dict[str, Any]) -> None:
    now = time.time()
    now_monotonic = time.monotonic()
    data = payload.get("data", {})
    with client.lock:
        client.osd_data["latitude"] = data.get("latitude")
        client.osd_data["longitude"] = data.get("longitude")
        height = data.get("height")
        client.osd_data["height"] = height
        if height is not None and client.takeoff_height is None:
            client.takeoff_height = height
        client.osd_data["attitude_head"] = data.get("attitude_head")
        client.osd_data["horizontal_speed"] = data.get("horizontal_speed")
        client.osd_data["speed_x"] = data.get("speed_x")
        client.osd_data["speed_y"] = data.get("speed_y")
        client.osd_data["speed_z"] = data.get("speed_z")
        client._last_osd_time = now
        client._last_osd_msg_monotonic = now_monotonic
        client._osd_timestamps.append(now)
        while client._osd_timestamps and (now - client._osd_timestamps[0]) > client._freq_window:
            client._osd_timestamps.pop(0)
    for callback in client.osd_callbacks:
        try:
            callback()
        except Exception:
            pass


def _handle_hsi(client, payload: dict[str, Any]) -> None:
    data = payload.get("data", {})
    around_distances = [
        parsed
        for item in data.get("around_distances", [])
        if (parsed := _to_optional_int(item)) is not None
    ]
    with client.lock:
        down_distance = _to_optional_int(data.get("down_distance"))
        client.osd_data["down_distance"] = down_distance
        client.osd_data["down_enable"] = data.get("down_enable")
        client.osd_data["down_work"] = data.get("down_work")
        client.hsi_data.update(
            {
                "around_distances": around_distances,
                "up_distance": _to_optional_int(data.get("up_distance")),
                "down_distance": down_distance,
                "timestamp": _to_optional_int(payload.get("timestamp")),
                "seq": _to_optional_int(payload.get("seq")),
            }
        )
        for name in (
            "up_enable",
            "up_work",
            "down_enable",
            "down_work",
            "left_enable",
            "left_work",
            "right_enable",
            "right_work",
            "front_enable",
            "front_work",
            "back_enable",
            "back_work",
            "vertical_enable",
            "vertical_work",
            "horizontal_enable",
            "horizontal_work",
        ):
            client.hsi_data[name] = data.get(name)
        client._last_hsi_msg_monotonic = time.monotonic()


def _handle_battery(client, payload: dict[str, Any]) -> None:
    with client.lock:
        client.osd_data["battery_percent"] = payload.get("data", {}).get("capacity_percent")
        client._last_battery_msg_monotonic = time.monotonic()


def _handle_drone_state(client, payload: dict[str, Any]) -> None:
    data = payload.get("data", {})
    limit = data.get("limit", {})
    with client.lock:
        client.drone_state["mode_code"] = data.get("mode_code")
        client.drone_state["rth_altitude"] = data.get("rth_altitude")
        client.drone_state["distance_limit"] = limit.get("distance_limit")
        client.drone_state["height_limit"] = limit.get("height_limit")
        client.drone_state["is_in_fixed_speed"] = data.get("is_in_fixed_speed")
        client.drone_state["night_lights_state"] = data.get("night_lights_state")


def _handle_camera_osd(client, payload: dict[str, Any]) -> None:
    data = payload.get("data", {})
    ir_lense = data.get("ir_lense", {})
    zoom_lense = data.get("zoom_lense", {})
    with client.lock:
        client.camera_osd["payload_index"] = data.get("payload_index")
        client.camera_osd["gimbal_pitch"] = data.get("gimbal_pitch")
        client.camera_osd["gimbal_roll"] = data.get("gimbal_roll")
        client.camera_osd["gimbal_yaw"] = data.get("gimbal_yaw")
        if isinstance(ir_lense, dict):
            client.camera_osd["screen_split_enable"] = ir_lense.get("screen_split_enable")
            client.camera_osd["ir_zoom_factor"] = ir_lense.get("ir_zoom_factor")
        if isinstance(zoom_lense, dict):
            client.camera_osd["zoom_factor"] = zoom_lense.get("zoom_factor")


def _handle_flyto_progress(client, payload: dict[str, Any]) -> None:
    data = payload.get("data", {})
    with client.lock:
        for name in (
            "fly_to_id",
            "status",
            "result",
            "way_point_index",
            "remaining_distance",
            "remaining_time",
            "planned_path_points",
        ):
            client.flyto_progress[name] = data.get(name)


def _handle_service_response(client, payload: dict[str, Any], console) -> None:
    tid = payload.get("tid")
    if not tid:
        return
    with client.lock:
        future = client.pending_requests.pop(tid, None)
    if not future:
        return
    error = _service_error(payload)
    if error is not None:
        label, value, message = error
        console.print(
            "[red]✗[/red] 服务调用错误 "
            f"(method={payload.get('method')}, tid={tid[:8]}..., {label}={value}, message={message})"
        )
        future.set_exception(Exception(f"{message} ({label}={value}, tid={tid})"))
        return
    console.print(f"[green]←[/green] 收到响应 (tid: {tid[:8]}...)")
    future.set_result(payload.get("data", {}))


def _service_error(payload: dict[str, Any]) -> tuple[str, Any, str] | None:
    info = payload.get("info", {})
    data = payload.get("data", {})
    top_result = payload.get("result")
    info_code = info.get("code") if isinstance(info, dict) else None
    data_result = data.get("result") if isinstance(data, dict) else None
    if info and info_code not in (None, 0):
        return ("info.code", info_code, info.get("message", "Unknown error"))
    if top_result not in (None, 0):
        output = data.get("output", {}) if isinstance(data, dict) else {}
        return ("result", top_result, _message(payload, output))
    if "result" in data and data_result != 0:
        output = data.get("output", {})
        return ("data.result", data_result, _message(data, output))
    return None


def _message(container: dict[str, Any], output: Any) -> str:
    return (
        container.get("message")
        or (output.get("msg") if isinstance(output, dict) else None)
        or (output.get("message") if isinstance(output, dict) else None)
        or (json.dumps(output, ensure_ascii=False) if output not in ({}, None) else None)
        or "Unknown error"
    )

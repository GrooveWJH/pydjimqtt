"""One-shot camera and gimbal actions."""

from pydjimqtt import camera_aim, camera_look_at, change_live_lens, reset_gimbal, set_camera_zoom

from . import state


def _payload_index(drone_state: dict) -> str:
    return drone_state["mqtt"].get_payload_index() or "88-0-0"


def gimbal_center() -> None:
    def action(_callsign: str, drone_state: dict) -> None:
        reset_gimbal(drone_state["mqtt"], _payload_index(drone_state), 0)

    state.parallel_run("云台回中", action)


def gimbal_down() -> None:
    def action(_callsign: str, drone_state: dict) -> None:
        reset_gimbal(drone_state["mqtt"], _payload_index(drone_state), 1)

    state.parallel_run("云台向下", action)


def lookat_ground() -> None:
    def action(_callsign: str, drone_state: dict) -> None:
        lat, lon, height = drone_state["mqtt"].get_position()
        if not lat:
            raise Exception("无GPS")
        camera_look_at(
            drone_state["mqtt"],
            _payload_index(drone_state),
            lat,
            lon,
            (height or 0) - 100,
            False,
        )

    state.parallel_run("看地面", action)


def zoom_in() -> None:
    state.parallel_run("放大", lambda callsign, drone_state: _change_zoom(callsign, drone_state, 1))


def zoom_out() -> None:
    state.parallel_run(
        "缩小", lambda callsign, drone_state: _change_zoom(callsign, drone_state, -1)
    )


def _change_zoom(callsign: str, drone_state: dict, direction: int) -> None:
    if drone_state["config"]["camera_type"] != "zoom":
        state.log(f"  - {callsign}: 广角模式不支持变焦")
        return
    zoom = drone_state["config"]["zoom"]
    zoom["current"] = max(zoom["min"], min(zoom["current"] + direction * zoom["step"], zoom["max"]))
    set_camera_zoom(drone_state["mqtt"], _payload_index(drone_state), zoom["current"], "zoom")
    state.log(f"  {callsign}: {zoom['current']}x")


def toggle_camera_type() -> None:
    def action(callsign: str, drone_state: dict) -> None:
        new_type = "wide" if drone_state["config"]["camera_type"] == "zoom" else "zoom"
        payload_index = _payload_index(drone_state)
        video_id = f"{drone_state['mqtt'].gateway_sn}/{payload_index}/normal-0"
        change_live_lens(drone_state["caller"], video_id, new_type)
        drone_state["config"]["camera_type"] = new_type
        state.log(f"  {callsign}: {'广角' if new_type == 'wide' else '变焦'}")

    state.parallel_run("切换镜头", action)


def aim_down_once(drone_state: dict) -> None:
    camera_aim(
        drone_state["mqtt"],
        _payload_index(drone_state),
        x=0.5,
        y=1.0,
        camera_type=drone_state["config"]["camera_type"],
        locked=False,
    )

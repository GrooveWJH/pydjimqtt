"""
DJI 服务模块
"""
from .commands import (
    request_control_auth,
    release_control_auth,
    enter_drc_mode,
    exit_drc_mode,
    change_live_lens,
    set_live_quality,
    start_live_push,
    stop_live_push,
    return_home,
    fly_to_point,
    send_stick_control,
    reset_gimbal,
    setup_drc_connection,
    setup_multiple_drc_connections,
)
from .heartbeat import start_heartbeat, stop_heartbeat
from .drc_commands import send_stick_control, set_camera_zoom, camera_look_at, camera_aim
from .connection_manager import DRCConnectionManager, ConnectionState

__all__ = [
    # 控制权
    'request_control_auth',
    'release_control_auth',
    # DRC 模式
    'enter_drc_mode',
    'exit_drc_mode',
    # 直播
    'change_live_lens',
    'set_live_quality',
    'start_live_push',
    'stop_live_push',
    # 飞行控制
    'return_home',
    'fly_to_point',
    # 心跳
    'start_heartbeat',
    'stop_heartbeat',
    # DRC 杆量控制
    'send_stick_control',
    # 相机和云台控制
    'set_camera_zoom',
    'camera_look_at',
    'camera_aim',
    'reset_gimbal',
    # DRC 连接设置
    'setup_drc_connection',
    'setup_multiple_drc_connections',
    # 连接管理
    'DRCConnectionManager',
    'ConnectionState',
]

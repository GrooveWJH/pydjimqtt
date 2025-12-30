"""
DJI DRC Python SDK

简洁实用的 DJI 无人机远程控制工具包
"""
from .core import MQTTClient, ServiceCaller
from .services import (
    request_control_auth,
    release_control_auth,
    enter_drc_mode,
    exit_drc_mode,
    change_live_lens,
    start_live_push,
    stop_live_push,
    return_home,
    fly_to_point,
    start_heartbeat,
    stop_heartbeat,
    send_stick_control,
    set_camera_zoom,
    take_photo,
    take_photo_wait,
    camera_look_at,
    camera_aim,
    reset_gimbal,
    setup_drc_connection,
    setup_multiple_drc_connections,
    DRCConnectionManager,
    ConnectionState,
)
from .utils import (
    print_json_message,
    get_key,
    wait_for_camera_data,
    build_video_id,
)
from .live_utils import (
    start_live,
    stop_live,
    set_live_quality,  # 使用带详细日志的版本
    zoom_control_loop,
)
from .primitives import (
    wait_for_condition,
    send_stick_repeatedly,
    fly_to_waypoint,
    monitor_flyto_progress,
)
from .tasks import (
    MissionRunner,
    run_parallel_missions,
    cleanup_missions,
    create_takeoff_mission,
    load_trajectory,
    fly_trajectory_sequence,
    create_trajectory_mission,
    create_takeoff_table,
    create_trajectory_table,
)

__version__ = '1.0.0'

__all__ = [
    # Core
    'MQTTClient',
    'ServiceCaller',
    # Services
    'request_control_auth',
    'release_control_auth',
    'enter_drc_mode',
    'exit_drc_mode',
    'change_live_lens',
    'set_live_quality',
    'start_live_push',
    'stop_live_push',
    'return_home',
    'fly_to_point',
    'start_heartbeat',
    'stop_heartbeat',
    'send_stick_control',
    'set_camera_zoom',
    'take_photo',
    'take_photo_wait',
    'camera_look_at',
    'camera_aim',
    'reset_gimbal',
    'setup_drc_connection',
    'setup_multiple_drc_connections',
    'DRCConnectionManager',
    'ConnectionState',
    # Utils
    'print_json_message',
    'get_key',
    'wait_for_camera_data',
    'build_video_id',
    # Live Utils
    'start_live',
    'stop_live',
    'zoom_control_loop',
    # Primitives
    'wait_for_condition',
    'send_stick_repeatedly',
    'fly_to_waypoint',
    'monitor_flyto_progress',
    # Tasks
    'MissionRunner',
    'run_parallel_missions',
    'cleanup_missions',
    'create_takeoff_mission',
    'load_trajectory',
    'fly_trajectory_sequence',
    'create_trajectory_mission',
    'create_takeoff_table',
    'create_trajectory_table',
]

# 服务方法

以下为常用服务的功能概览，具体参数可参照源码与样例。

## 控制权

- `request_control_auth(caller, user_id, user_callsign)`
- `release_control_auth(caller)`

## DRC 模式

- `enter_drc_mode(caller, mqtt_broker, osd_frequency, hsi_frequency)`
- `exit_drc_mode(caller)`

## 直播

- `start_live_push(caller, url, video_id)`
- `stop_live_push(caller, video_id)`
- `change_live_lens(caller, video_id, video_type)`
- `set_live_quality(caller, video_quality)`

## 飞行控制

- `send_stick_control(caller, roll, pitch, yaw, throttle)`
- `fly_to_point(caller, latitude, longitude, height, max_speed)`
- `return_home(caller)`

## 相机/云台

- `set_camera_zoom(caller, zoom_factor)`
- `camera_look_at(caller, gimbal_pitch, gimbal_yaw)`
- `camera_aim(caller, yaw, pitch)`
- `reset_gimbal(caller)`

## 连接管理工具

- `setup_drc_connection(...)`
- `setup_multiple_drc_connections(...)`
- `DRCConnectionManager`

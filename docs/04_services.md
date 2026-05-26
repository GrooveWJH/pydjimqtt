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
- `set_gimbal_pitch_async(mqtt_client, target_pitch, ...)`

`set_gimbal_pitch_async` 是云台 pitch 固定角度控制的公开入口。调用后立即返回
`GimbalPitchTask`，调用方可通过 `status()` 查询 `RUNNING`、`SUCCEEDED`、
`UNREACHABLE`、`FAILED` 四种状态，并通过 `result(timeout=...)` 获取
`GimbalPitchResult`。

目标角度采用度，表达操作者意图，范围为 `-90.0` 到 `90.0`。目标不会按具体机型的
物理上限静默截断；如果云台已接近物理限位且无法继续向目标角度收敛，结果状态为
`UNREACHABLE`。

控制器使用连续速度流模式：运动期间持续发送 `pitch_speed`，只在结束时发送一次
`pitch_speed=0`。默认 profile 已按实机标定结果配置为低延迟控制，可通过
`tools/calibrate_gimbal_pitch.py` 为网关序列号生成
`~/.config/pydjimqtt/gimbal_profiles/{gateway_sn}.json`，运行时会优先加载该 profile。

`GimbalPitchResult.trace` 记录每次控制迭代的速度、起止 pitch、进度和最终停机标记，
用于复盘过冲、卡顿或物理限位问题。

## 连接管理工具

- `setup_drc_connection(...)`
- `setup_multiple_drc_connections(...)`
- `DRCConnectionManager`

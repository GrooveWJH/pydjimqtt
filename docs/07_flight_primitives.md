# 飞行原语

SDK 提供基础控制原语，可直接组合为任务流。

## 摇杆控制

通过 `send_stick_control` 发送实时摇杆数据。

## 飞点

`fly_to_point` 让无人机飞往指定坐标。

```python
from pydjimqtt import fly_to_point

fly_to_point(caller, latitude=39.0, longitude=117.0, height=50.0, max_speed=8)
```

## 航点封装

`fly_to_waypoint` 是对飞点的轻量封装：

```python
from pydjimqtt import fly_to_waypoint

fly_to_waypoint(caller, lat=39.0, lon=117.0, height=50.0, max_speed=8)
```

## 进度监控

`monitor_flyto_progress` 读取并打印进度：

```python
from pydjimqtt import monitor_flyto_progress

status, progress = monitor_flyto_progress(mqtt, callsign="drone", show_progress=True)
```

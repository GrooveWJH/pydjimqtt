# pydjimqtt

> 设计哲学: 简洁实用，拒绝过度工程化

基于 MQTT 的 DJI Cloud API Python SDK，提供最小可用的连接与服务调用能力，并补充 DRC、直播、飞行与任务相关的常用封装。
目标是可读、易用、可组合。

## 功能概览

- MQTT 连接管理（订阅/响应、OSD/状态缓存）
- 服务调用封装（ServiceCaller）
- 控制权申请与释放
- DRC 模式进入/退出与心跳维护
- 直播推流、清晰度调整、镜头切换
- 飞点/航点原语与进度监控
- 相机与云台控制
- 任务与轨迹执行封装
- Mock 系统与基础测试脚本

## 环境要求

- Python >= 3.12
- 依赖：`paho-mqtt`、`rich` 等（见 `pyproject.toml`）

## 安装

推荐在 `pydjimqtt/` 目录下使用可编辑安装：

```bash
pip install -e .
```

临时运行也可以：

```bash
PYTHONPATH=./src python sample/01_connect_control.py
```

## 快速开始

最小示例（申请控制权）：

```python
from pydjimqtt import MQTTClient, ServiceCaller, request_control_auth, release_control_auth

MQTT_CONFIG = {
    "host": "127.0.0.1",
    "port": 1883,
    "username": "admin",
    "password": "password",
}
GATEWAY_SN = "YOUR_GATEWAY_SN"

mqtt = MQTTClient(gateway_sn=GATEWAY_SN, mqtt_config=MQTT_CONFIG)
mqtt.connect()
caller = ServiceCaller(mqtt)

try:
    request_control_auth(caller, user_id="pilot", user_callsign="callsign")
    input("请在遥控器上确认授权，然后回车继续...")
    release_control_auth(caller)
finally:
    mqtt.disconnect()
```

## 核心 API

### MQTTClient - MQTT 连接管理

```python
from pydjimqtt import MQTTClient

mqtt_config = {
    "host": "127.0.0.1",
    "port": 1883,
    "username": "admin",
    "password": "password",
}

mqtt = MQTTClient(gateway_sn="YOUR_GATEWAY_SN", mqtt_config=mqtt_config)
mqtt.connect()
```

### ServiceCaller - 服务调用封装

```python
from pydjimqtt import ServiceCaller

caller = ServiceCaller(mqtt, timeout=10)
result = caller.call("method_name", {"param": "value"})
```

### 控制权管理

```python
from pydjimqtt import request_control_auth, release_control_auth

request_control_auth(caller, user_id="pilot", user_callsign="callsign")
release_control_auth(caller)
```

### DRC 模式管理

```python
from pydjimqtt import enter_drc_mode, exit_drc_mode

mqtt_broker_config = {
    "address": "127.0.0.1:1883",
    "client_id": "drc-YOUR_GATEWAY_SN",
    "username": "admin",
    "password": "password",
    "expire_time": 1_700_000_000,
    "enable_tls": False,
}

enter_drc_mode(caller, mqtt_broker=mqtt_broker_config, osd_frequency=100, hsi_frequency=10)
exit_drc_mode(caller)
```

### 心跳维持

```python
from pydjimqtt import start_heartbeat, stop_heartbeat

heartbeat_thread = start_heartbeat(mqtt, interval=0.2)
stop_heartbeat(heartbeat_thread)
```

### 直播控制

```python
from pydjimqtt import change_live_lens, set_live_quality, start_live_push, stop_live_push

change_live_lens(caller, video_id="52-0-0", video_type="zoom")
set_live_quality(caller, video_quality=3)
start_live_push(caller, url="rtmp://localhost/live/test", video_id="52-0-0")
stop_live_push(caller, video_id="52-0-0")
```

## 样例脚本

位于 `sample/`：

- `sample/01_connect_control.py`: 连接并申请/释放控制权
- `sample/02_drc_heartbeat.py`: 进入 DRC 并维持心跳
- `sample/03_live_stream.py`: 启动/调整/停止直播
- `sample/04_fly_to_waypoint.py`: 飞点并监控进度

运行示例：

```bash
python sample/01_connect_control.py
```

## 文档

完整文档索引见：`docs/README.md`

推荐阅读顺序：

- `docs/00_overview.md`
- `docs/01_quickstart.md`
- `docs/05_drc_and_heartbeat.md`
- `docs/06_live_streaming.md`
- `docs/07_flight_primitives.md`

## 开发与调试

### 项目结构

```
pydjimqtt/
├── src/pydjimqtt            # SDK 代码
├── sample/               # 示例脚本
├── docs/                 # 文档
├── tests/                # 测试与 mock 脚本
├── tools/                # 工具脚本
└── utils/                # 通用工具
```

### Mock 系统

项目提供 mock 启动脚本：

```bash
./tests/start_mock_system.sh
```

### 测试

当前测试集中在 `tests/` 目录。
如需自定义测试，建议先确认 MQTT 可连接、控制权流程可跑通。

推荐使用 uv 环境运行 pytest（避免系统 pytest 插件冲突）：

```bash
uv run python -m pytest -q tests/test_api_smoke.py
```

## 常见问题

- `ModuleNotFoundError: pydjimqtt`: 先执行 `pip install -e .` 或使用 `PYTHONPATH=./src`
- MQTT 连接失败：检查 broker 地址、用户名密码与网络可达性
- DRC 进入失败：确认已申请控制权、`expire_time` 未过期

## License

内部项目，如需对外发布请补充许可说明。

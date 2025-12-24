# 快速开始

下面是最小可运行脚本：连接 MQTT 并申请控制权。

## 安装依赖

```bash
pip install paho-mqtt rich
```

## 最小示例

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

## 下一步

- DRC + 心跳：`docs/05_drc_and_heartbeat.md`
- 直播：`docs/06_live_streaming.md`
- 飞点与原语：`docs/07_flight_primitives.md`

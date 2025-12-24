# DRC 与心跳

DRC 模式用于低延迟控制，进入后必须持续发送心跳。

## 基本流程

1. 请求控制权。
2. `enter_drc_mode` 进入 DRC。
3. `start_heartbeat` 开始心跳循环。
4. 退出 DRC：`stop_heartbeat` + `exit_drc_mode`。

## 心跳建议

- 心跳频率推荐 5Hz（`interval=0.2`）。
- 心跳中断可能导致 DRC 失效。

## 示例

```python
from pydjimqtt import MQTTClient, ServiceCaller, request_control_auth
from pydjimqtt import enter_drc_mode, exit_drc_mode, start_heartbeat, stop_heartbeat
import time

mqtt = MQTTClient(gateway_sn=GATEWAY_SN, mqtt_config=MQTT_CONFIG)
mqtt.connect()
caller = ServiceCaller(mqtt)

try:
    request_control_auth(caller, user_id="pilot", user_callsign="callsign")
    input("确认控制权后回车...")
    enter_drc_mode(caller, mqtt_broker=MQTT_BROKER, osd_frequency=100, hsi_frequency=10)
    hb = start_heartbeat(mqtt, interval=0.2)
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    stop_heartbeat(hb)
    exit_drc_mode(caller)
    mqtt.disconnect()
```

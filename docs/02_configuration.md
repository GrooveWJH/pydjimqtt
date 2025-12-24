# 配置说明

本 SDK 主要依赖 MQTT 连接配置和网关设备 SN。

## 基本配置

```python
MQTT_CONFIG = {
    "host": "127.0.0.1",
    "port": 1883,
    "username": "admin",
    "password": "password",
}
GATEWAY_SN = "YOUR_GATEWAY_SN"
```

字段说明：

- host: MQTT broker 地址
- port: MQTT broker 端口
- username/password: MQTT 登录凭据
- GATEWAY_SN: DJI 网关序列号，用于拼接主题和调用

## DRC broker 配置

进入 DRC 模式需要单独的 broker 配置：

```python
mqtt_broker = {
    "address": f"{MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}",
    "client_id": f"drc-{GATEWAY_SN}",
    "username": MQTT_CONFIG["username"],
    "password": MQTT_CONFIG["password"],
    "expire_time": 1700000000,
    "enable_tls": False,
}
```

## 运行环境

- Python 3.10+ 建议
- 依赖：`paho-mqtt`、`rich`

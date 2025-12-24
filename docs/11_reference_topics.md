# MQTT 主题与消息参考

以下为 SDK 主要订阅/发布的主题结构（以 GATEWAY_SN 为例）。

## 服务请求与响应

- 请求：`thing/product/{GATEWAY_SN}/services`
- 响应：`thing/product/{GATEWAY_SN}/services_reply`

## DRC 数据上行

- 上行：`thing/product/{GATEWAY_SN}/drc/up`

## 状态与事件

- 设备状态：`sys/product/{GATEWAY_SN}/status`
- 事件：`thing/product/{GATEWAY_SN}/events`

## 消息结构

服务请求常见结构：

```json
{
  "tid": "uuid",
  "method": "method_name",
  "timestamp": 1700000000000,
  "data": {
    "param": "value"
  }
}
```

服务响应常见结构：

```json
{
  "tid": "uuid",
  "method": "method_name",
  "data": {
    "result": 0,
    "output": {}
  }
}
```

具体字段以 DJI Cloud API 文档与设备固件为准。

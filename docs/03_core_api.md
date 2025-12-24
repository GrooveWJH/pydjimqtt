# 核心 API

## MQTTClient

负责 MQTT 连接、订阅和接收消息，内部维护 OSD/状态缓存。

常用方法：

- `connect()` 连接并订阅相关主题
- `disconnect()` 断开连接
- `get_latitude()/get_longitude()/get_height()` 读取最新 OSD
- `get_flyto_progress()` 读取飞点进度

## ServiceCaller

封装请求/响应式服务调用。

常用方法：

- `call(method, data)` 发送服务请求并等待响应

## 生命周期建议

1. MQTT 连接成功后再创建 ServiceCaller。
2. 申请控制权后再进入 DRC。
3. 退出 DRC 后停止心跳并断开 MQTT。

## 错误处理

- MQTT 连接失败会抛异常。
- 服务调用失败通常体现在 `result` 字段不为 0。
- 推荐在关键流程加 `try/finally`，确保 `disconnect()` 被调用。

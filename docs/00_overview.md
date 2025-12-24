# 概览

本 SDK 提供一个尽量精简的 DJI Cloud API Python 接口，核心以 MQTT 通讯为基础。
它强调可组合的最小能力：连接、服务调用、控制权、DRC 模式、直播、飞行指令等。

## 典型工作流

1. 创建 MQTTClient 并连接。
2. 创建 ServiceCaller 进行请求/响应调用。
3. 申请控制权。
4. 进入 DRC 模式并启动心跳。
5. 发送控制指令（摇杆、飞点、相机、直播）。
6. 退出 DRC、断开连接。

## 从哪里开始

- 入门：`docs/01_quickstart.md`
- 直接跑示例：`sample/` 目录

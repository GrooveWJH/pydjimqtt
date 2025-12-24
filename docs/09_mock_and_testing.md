# Mock 与测试

项目内包含 Mock 系统与测试脚本，用于在没有真实设备时进行联调。

## 启动 Mock 系统

- `start_mock_system.sh`
- `tests/start_mock_system.sh`

根据实际环境执行脚本，确保 MQTT broker 可用。

## 测试思路

- 先验证 MQTT 连接。
- 再验证控制权与 DRC。
- 最后验证飞行/直播等高层功能。

如需更细的 mock 数据或主题模拟，请扩展 `pydjimqtt/mock/`。

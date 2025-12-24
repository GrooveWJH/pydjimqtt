# 任务与轨迹

SDK 提供任务级别的封装，用于组织多步骤飞行或轨迹执行。

## MissionRunner

`MissionRunner` 用于串行执行任务列表，便于统一清理。

## 轨迹任务

- `load_trajectory`: 读取轨迹文件
- `create_trajectory_mission`: 创建轨迹任务
- `fly_trajectory_sequence`: 执行轨迹序列

## 表格构建

- `create_takeoff_table`
- `create_trajectory_table`

## 示例思路

1. 读取轨迹数据。
2. 生成任务序列。
3. 通过 MissionRunner 执行。
4. 清理任务状态。

具体参数请参照 `pydjimqtt/tasks/` 目录源码。

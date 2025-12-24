# 直播推流

SDK 支持通过服务接口发起/停止直播，并可设置清晰度或切换镜头。

## 基本流程

1. 申请控制权。
2. 调用 `start_live_push` 或使用 `start_live` 工具函数。
3. 按需 `set_live_quality` 与 `change_live_lens`。
4. 使用 `stop_live_push` 或 `stop_live` 结束。

## 使用工具函数

`pydjimqtt.live_utils` 提供更详细的日志输出：

```python
from pydjimqtt import start_live, stop_live, set_live_quality

video_id = start_live(caller, mqtt, rtmp_url, video_index="normal-0", video_quality=3)
if video_id:
    set_live_quality(caller, video_id, video_quality=3)
    stop_live(caller, video_id)
```

## RTMP 注意事项

- 确保 RTMP 服务器可达。
- URL 形如 `rtmp://host/live/stream`。
- 根据带宽选择合适清晰度。

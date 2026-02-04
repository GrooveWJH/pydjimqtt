"""
等待条件原语
"""

import time
from typing import Callable


def wait_for_condition(
    condition_func: Callable[[], bool],
    timeout: float = 30.0,
    check_interval: float = 0.5,
    timeout_msg: str = "等待超时",
) -> None:
    """
    等待条件满足（通用等待模式）

    Args:
        condition_func: 返回布尔值的条件函数
        timeout: 超时时间（秒）
        check_interval: 检查间隔（秒）
        timeout_msg: 超时错误消息

    Raises:
        TimeoutError: 超时未满足条件

    Example:
        >>> # 等待GPS数据就绪
        >>> wait_for_condition(lambda: mqtt.get_height() is not None, timeout=30)
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_func():
            return
        time.sleep(check_interval)
    raise TimeoutError(timeout_msg)

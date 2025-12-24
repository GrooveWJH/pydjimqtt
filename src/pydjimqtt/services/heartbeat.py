"""
DRC 心跳维持服务
"""
import time
import json
import threading
from ..core import MQTTClient
from rich.console import Console

console = Console()


def start_heartbeat(
    mqtt_client: MQTTClient,
    interval: float = 0.2
) -> threading.Thread:
    """
    启动 DRC 心跳后台线程

    Args:
        mqtt_client: MQTT 客户端
        interval: 心跳间隔（秒）

    Returns:
        心跳线程对象（调用者负责在程序退出时停止）

    示例:
        >>> thread = start_heartbeat(mqtt, interval=0.2)
        >>> # ... 做你的事情 ...
        >>> stop_heartbeat(thread)
    """
    topic = f"thing/product/{mqtt_client.gateway_sn}/drc/down"
    stop_flag = threading.Event()

    def heartbeat_loop():
        """心跳循环 - 使用精确定时"""
        next_tick = time.perf_counter()
        seq = int(time.time() * 1000)

        while not stop_flag.is_set():
            now = time.perf_counter()
            if now < next_tick:
                time.sleep(min(interval, next_tick - now))
                continue

            # 构建心跳消息
            seq += 1
            payload = {
                "seq": seq,
                "method": "heart_beat",
                "data": {"timestamp": int(time.time() * 1000)},
            }

            # 发送心跳（QoS 0，不等待响应）
            try:
                mqtt_client.client.publish(topic, json.dumps(payload), qos=0)
            except Exception as e:
                console.print(f"[yellow]心跳发送失败: {e}[/yellow]")

            # 计算下一次发送时间
            next_tick += interval
            if next_tick < now:
                next_tick = now + interval

    # 创建并启动线程
    thread = threading.Thread(target=heartbeat_loop, daemon=True)
    thread.stop_flag = stop_flag  # 存储停止标志，供 stop_heartbeat 使用
    thread.start()

    console.print(f"[green]✓ 心跳已启动 (间隔: {interval}s, 频率: {1.0/interval:.1f}Hz)[/green]")
    return thread


def stop_heartbeat(thread: threading.Thread):
    """
    停止心跳线程

    Args:
        thread: 由 start_heartbeat 返回的线程对象
    """
    if hasattr(thread, 'stop_flag'):
        thread.stop_flag.set()
        thread.join(timeout=5)

        # 检查线程是否正常退出
        if thread.is_alive():
            console.print("[red]⚠ 心跳线程未能正常退出[/red]")
        else:
            console.print("[yellow]心跳已停止[/yellow]")

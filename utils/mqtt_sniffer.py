#!/usr/bin/env python3
"""
DJI MQTT 嗅探器 - 多 Topic 监听和消息捕获工具

基于 pydjimqtt 统一的 DRC 连接函数，简化连接流程。

功能：
1. 支持同时监听多个 MQTT topic
2. 使用 setup_drc_connection 自动完成 DRC 模式设置
3. 实时显示各 topic 消息统计（类型、数量、频率）
4. 按 topic 分类保存消息到独立 JSON 文件
5. 输出到规范的目录结构

使用方法：
    # 从任意位置运行
    python utils/mqtt_sniffer.py

    # 或从项目根目录运行
    python pythonSDK/utils/mqtt_sniffer.py

架构说明：
    - 使用 pydjimqtt.setup_drc_connection() 一键建立 DRC 连接
    - 自动处理：MQTT 连接、控制权请求、DRC 模式进入、心跳启动
    - 所有错误处理由 pydjimqtt 统一管理
"""
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, List

# 动态路径解析 - 支持从任意位置运行
script_dir = Path(__file__).resolve().parent
parent_dir = script_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.columns import Columns
# 导入重构后的 pydjimqtt - 使用统一的 DRC 连接函数
from pydjimqtt import MQTTClient, setup_drc_connection, stop_heartbeat

# ======== 配置 ========
MQTT_CONFIG = {'host': '81.70.222.38', 'port': 1883, 'username': 'dji', 'password': 'lab605605'}
GATEWAY_SN = "9N9CN2J0012CXY"  # 9N9CN2J0012CXY (001) | 9N9CN8400164WH (002) | 9N9CN180011TJN (003)
USER_ID, USER_CALLSIGN = "groove", "吴建豪"

# DRC 模式参数
OSD_FREQUENCY, HSI_FREQUENCY = 1, 1  # Hz
HEARTBEAT_INTERVAL = 1.0  # 秒

# 嗅探配置
ENABLE_DRC_MODE = True  # 是否自动进入 DRC 模式
SNIFF_TOPICS = [
    f"sys/product/{GATEWAY_SN}/status",         # 设备状态
    f"thing/product/{GATEWAY_SN}/events_reply", # 事件回复
    f"thing/product/{GATEWAY_SN}/drc/up",       # DRC 上行数据
    f"sys/product/{GATEWAY_SN}/network/probe",       # DRC 上行数据
]
OUTPUT_BASE_DIR = "data/sniffed_data"  # 输出根目录
# ======== 配置结束 ========


class TopicSniffer:
    """
    多 Topic MQTT 嗅探器

    职责：
    - 监听多个 MQTT topic
    - 统计消息类型、频率
    - 保存原始消息数据

    设计：
    - 包装 MQTTClient 的 on_message 回调
    - 不干扰 pydjimqtt 的正常服务响应处理
    - 独立统计每个 topic 的数据
    """

    def __init__(self, mqtt_client: MQTTClient, topics: List[str]):
        self.mqtt = mqtt_client
        self.topics = topics
        # 为每个 topic 维护独立的统计信息
        self.topic_stats: Dict[str, Dict[str, Any]] = {}
        for topic in topics:
            self.topic_stats[topic] = {
                'message_counts': defaultdict(int), 'latest_messages': {},
                'first_time': {}, 'last_time': {}, 'total_count': 0,
            }
        self.start_time = time.time()
        # 包装原始消息处理器（保留 pydjimqtt 的响应处理逻辑）
        self._original_on_message = mqtt_client.client.on_message
        mqtt_client.client.on_message = self._on_message_wrapper
        # 订阅所有嗅探 topic
        for topic in topics:
            mqtt_client.client.subscribe(topic, qos=0)

    def _on_message_wrapper(self, client, userdata, msg):
        """
        消息处理包装器 - 先调用原始处理器，再捕获嗅探数据

        这样可以确保：
        1. pydjimqtt 的服务响应处理正常工作（MQTTClient._on_message）
        2. 嗅探器不干扰正常的请求-响应流程
        3. 同时捕获所有监听 topic 的消息数据
        """
        if self._original_on_message:  # 优先让 pydjimqtt 处理服务响应（/services_reply）
            self._original_on_message(client, userdata, msg)
        # 嗅探器捕获监听的 topic
        if msg.topic in self.topics:
            try:
                payload = json.loads(msg.payload.decode())
                method = payload.get('method', payload.get('event_name', 'unknown'))  # 兼容不同格式
                stats = self.topic_stats[msg.topic]
                now = time.time()
                # 更新统计信息
                stats['message_counts'][method] += 1
                stats['latest_messages'][method] = payload
                stats['last_time'][method] = now
                stats['total_count'] += 1
                if method not in stats['first_time']:
                    stats['first_time'][method] = now
            except Exception:
                pass  # 解析失败的消息静默跳过（可能是二进制数据或其他格式）

    def get_frequency(self, topic: str, method: str) -> float:
        """计算消息频率（Hz）"""
        stats = self.topic_stats[topic]
        if method not in stats['first_time'] or method not in stats['last_time']:
            return 0.0
        count = stats['message_counts'][method]
        if count <= 1:
            return 0.0
        time_span = stats['last_time'][method] - stats['first_time'][method]
        return (count - 1) / time_span if time_span > 0 else 0.0

    def render_status(self) -> Panel:
        """渲染实时监控面板 - 显示每个 topic 的消息统计表格、消息类型、数量、频率"""
        tables, total_messages = [], 0
        for topic in self.topics:
            stats = self.topic_stats[topic]
            total_messages += stats['total_count']
            topic_short = topic.split('/')[-1] if '/' in topic else topic
            table = Table(title=f"[cyan]{topic_short}[/cyan]", show_header=True, header_style="bold yellow", expand=True, box=None)
            table.add_column("消息类型", style="cyan", width=35)
            table.add_column("次数", justify="right", style="yellow", width=8)
            table.add_column("频率", justify="right", style="green", width=12)
            for method in sorted(stats['message_counts'].keys()):
                count = stats['message_counts'][method]
                freq = self.get_frequency(topic, method)
                freq_str = f"{freq:.2f}Hz" if freq > 0 else "-"
                table.add_row(method, str(count), freq_str)
            if stats['total_count'] > 0:
                tables.append(table)
        combined = Columns(tables, equal=True, expand=True) if tables else "[dim]暂无消息[/dim]"
        runtime = time.time() - self.start_time
        summary = " | ".join([
            f"[bold]运行时间[/bold]: {runtime:.1f}秒",
            f"[bold]总消息数[/bold]: {total_messages}",
            f"[bold]监听主题[/bold]: {len(self.topics)}"
        ])
        return Panel(combined, title="[bold cyan]DJI MQTT 嗅探器[/bold cyan]", subtitle=summary, border_style="cyan")

    def save_to_directory(self, base_dir: str):
        """保存所有消息数据到分类目录"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = Path(base_dir) / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)
        # 为每个 topic 保存独立的 JSON 文件
        for topic in self.topics:
            stats = self.topic_stats[topic]
            if stats['total_count'] == 0:
                continue
            topic_name = topic.split('/')[-1] if '/' in topic else topic
            filename = output_dir / f"{topic_name}.json"
            output = {
                "metadata": {
                    "topic": topic, "gateway_sn": self.mqtt.gateway_sn,
                    "capture_time": datetime.now().isoformat(),
                    "runtime_seconds": time.time() - self.start_time,
                    "total_messages": stats['total_count'],
                    "message_types": len(stats['message_counts'])
                },
                "statistics": {
                    method: {
                        "count": stats['message_counts'][method],
                        "frequency_hz": self.get_frequency(topic, method),
                        "first_time": datetime.fromtimestamp(stats['first_time'][method]).isoformat() if method in stats['first_time'] else None,
                        "last_time": datetime.fromtimestamp(stats['last_time'][method]).isoformat() if method in stats['last_time'] else None
                    }
                    for method in sorted(stats['message_counts'].keys())
                },
                "latest_messages": stats['latest_messages']
            }
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
        # 保存汇总信息
        summary_file = output_dir / "_summary.json"
        summary = {
            "capture_info": {
                "gateway_sn": self.mqtt.gateway_sn,
                "capture_time": datetime.now().isoformat(),
                "runtime_seconds": time.time() - self.start_time,
                "topics": self.topics
            },
            "statistics": {
                topic.split('/')[-1]: {
                    "full_topic": topic,
                    "total_messages": self.topic_stats[topic]['total_count'],
                    "message_types": len(self.topic_stats[topic]['message_counts']),
                    "methods": list(self.topic_stats[topic]['message_counts'].keys())
                }
                for topic in self.topics
            }
        }
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        return output_dir


def main() -> int:
    """主函数 - 使用 setup_drc_connection 简化连接流程"""
    console = Console()
    mqtt, heartbeat = None, None

    try:
        # ========== 1. 建立 DRC 连接（或仅 MQTT 连接）==========
        console.rule("[bold cyan]建立连接[/bold cyan]")

        if ENABLE_DRC_MODE:
            # 使用统一的 DRC 连接函数（自动完成：连接 MQTT、请求控制权、进入 DRC、启动心跳）
            mqtt, _, heartbeat = setup_drc_connection(
                gateway_sn=GATEWAY_SN,
                mqtt_config=MQTT_CONFIG,
                user_id=USER_ID,
                user_callsign=USER_CALLSIGN,
                osd_frequency=OSD_FREQUENCY,
                hsi_frequency=HSI_FREQUENCY,
                heartbeat_interval=HEARTBEAT_INTERVAL,
                wait_for_user=True  # 等待用户在 DJI Pilot 上授权
            )
        else:
            # 仅连接 MQTT，不进入 DRC 模式
            console.print("[yellow]跳过 DRC 模式，仅连接 MQTT[/yellow]")
            mqtt = MQTTClient(GATEWAY_SN, MQTT_CONFIG)
            mqtt.connect()

        # ========== 2. 启动嗅探器 ==========
        console.rule("[bold cyan]启动 MQTT 嗅探器[/bold cyan]")
        console.print(f"[bold green]正在监听 {len(SNIFF_TOPICS)} 个 topic...[/bold green]")
        console.print("[bold yellow]按 Ctrl+C 停止嗅探、保存数据并退出。[/bold yellow]\n")
        sniffer = TopicSniffer(mqtt, SNIFF_TOPICS)

        # ========== 3. 实时显示监控面板 ==========
        with Live(sniffer.render_status(), refresh_per_second=2, console=console) as live:
            while True:
                time.sleep(0.5)
                live.update(sniffer.render_status())

    except KeyboardInterrupt:
        console.print("\n[yellow]检测到中断，正在停止...[/yellow]")

    except Exception as e:
        console.print(f"\n[bold red]✗ 错误: {e}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        return 1

    finally:
        # ========== 4. 清理资源 ==========
        if heartbeat:
            console.print("[cyan]停止心跳...[/cyan]")
            stop_heartbeat(heartbeat)

        if mqtt:
            console.print(f"[cyan]正在保存消息数据到 {OUTPUT_BASE_DIR}/...[/cyan]")
            output_dir = sniffer.save_to_directory(OUTPUT_BASE_DIR)
            console.print(f"[green]✓ 数据已保存到 {output_dir}/[/green]")

            saved_files = list(output_dir.glob("*.json"))
            if saved_files:
                console.print("\n[bold cyan]已保存文件：[/bold cyan]")
                for file in sorted(saved_files):
                    size = file.stat().st_size
                    console.print(f"  [green]→[/green] {file.name} ({size:,} bytes)")

            console.print("[cyan]断开 MQTT 连接...[/cyan]")
            mqtt.disconnect()

    console.print("[green]✓ 嗅探完成[/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())

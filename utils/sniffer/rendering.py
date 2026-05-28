"""Rich rendering for the MQTT sniffer."""

import time

from rich.columns import Columns
from rich.panel import Panel
from rich.table import Table


def render_status(sniffer) -> Panel:
    tables, total_messages = [], 0
    for topic in sniffer.topics:
        stats = sniffer.topic_stats[topic]
        total_messages += stats["total_count"]
        topic_short = topic.split("/")[-1] if "/" in topic else topic
        table = Table(
            title=f"[cyan]{topic_short}[/cyan]",
            show_header=True,
            header_style="bold yellow",
            expand=True,
            box=None,
        )
        table.add_column("消息类型", style="cyan", width=35)
        table.add_column("次数", justify="right", style="yellow", width=8)
        table.add_column("频率", justify="right", style="green", width=12)
        for method in sorted(stats["message_counts"].keys()):
            count = stats["message_counts"][method]
            freq = sniffer.get_frequency(topic, method)
            freq_str = f"{freq:.2f}Hz" if freq > 0 else "-"
            table.add_row(method, str(count), freq_str)
        if stats["total_count"] > 0:
            tables.append(table)

    combined = Columns(tables, equal=True, expand=True) if tables else "[dim]暂无消息[/dim]"
    runtime = time.time() - sniffer.start_time
    summary = " | ".join(
        [
            f"[bold]运行时间[/bold]: {runtime:.1f}秒",
            f"[bold]总消息数[/bold]: {total_messages}",
            f"[bold]监听主题[/bold]: {len(sniffer.topics)}",
        ]
    )
    return Panel(
        combined,
        title="[bold cyan]DJI MQTT 嗅探器[/bold cyan]",
        subtitle=summary,
        border_style="cyan",
    )

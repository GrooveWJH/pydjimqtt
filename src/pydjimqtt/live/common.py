from __future__ import annotations

import time
import uuid
from typing import Any

from rich.console import Console

from ..utils import print_json_message

console = Console()


def call_live_service(caller, method: str, request_data: dict[str, Any], title: str) -> dict | None:
    tid = str(uuid.uuid4())
    full_request = {
        "bid": tid,
        "data": request_data,
        "tid": tid,
        "timestamp": int(time.time() * 1000),
        "method": method,
    }
    print_json_message(f"📤 发送 MQTT 请求 ({method})", full_request, "blue")
    try:
        result = caller.call(method, request_data)
    except Exception as exc:
        console.print(f"\n[bold red]✗ 请求异常: {exc}[/bold red]")
        return None

    full_response = {
        "bid": tid,
        "data": result,
        "tid": tid,
        "timestamp": int(time.time() * 1000),
        "method": method,
    }
    print_json_message(f"📥 接收 MQTT 响应 ({method})", full_response, "green")
    if result.get("result") == 0:
        return result
    console.print(f"\n[bold red]✗ {title}失败[/bold red]")
    console.print(f"[red]错误码: {result.get('result', 'unknown')}[/red]")
    console.print(f"[red]错误信息: {result.get('message', '无错误信息')}[/red]")
    return None


def print_output(result: dict) -> None:
    output = result.get("output", {})
    if output:
        console.print(f"[dim]输出信息: {output}[/dim]")

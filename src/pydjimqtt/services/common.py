from __future__ import annotations

import json
from typing import Any

from rich.console import Console

from ..core import MQTTClient, ServiceCaller

console = Console()


def publish_drc_down(mqtt_client: MQTTClient, payload: dict[str, Any]) -> None:
    if mqtt_client.client is None:
        raise RuntimeError("MQTT client is not connected")
    topic = f"thing/product/{mqtt_client.gateway_sn}/drc/down"
    mqtt_client.client.publish(topic, json.dumps(payload), qos=0)


def call_service(
    caller: ServiceCaller,
    method: str,
    data: dict[str, Any] | None = None,
    success_msg: str | None = None,
) -> dict[str, Any]:
    try:
        result = caller.call(method, data or {})
        if result.get("result") == 0:
            if success_msg:
                console.print(f"[green]✓ {success_msg}[/green]")
            return result.get("data", {})

        error_code = result.get("result", "unknown")
        error_msg = result.get("message", result.get("output", {}).get("msg", "Unknown error"))
        console.print("[red]✗ 服务调用失败:[/red]")
        console.print(f"  [yellow]方法:[/yellow] {method}")
        console.print(f"  [yellow]错误码:[/yellow] {error_code}")
        console.print(f"  [yellow]错误信息:[/yellow] {error_msg}")
        console.print(f"  [dim]完整响应: {result}[/dim]")
        raise Exception(f"{method} 失败 (code={error_code}): {error_msg} | 完整响应: {result}")
    except Exception as exc:
        console.print(f"[red]✗ {method}: {exc}[/red]")
        raise

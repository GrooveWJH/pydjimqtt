#!/usr/bin/env python3
"""
MQTT 连接测试脚本

测试连接到远程 MQTT Broker 并验证用户名密码
"""
import paho.mqtt.client as mqtt
import time
from rich.console import Console
from rich.panel import Panel

console = Console()


def on_connect(client, userdata, flags, reason_code, properties):
    """连接回调（MQTT v5）"""
    # reason_code 是 ReasonCode 对象，需要取 value
    rc = reason_code.value if hasattr(reason_code, 'value') else reason_code

    if rc == 0:
        console.print("[bold green]✓ 连接成功！[/bold green]")
        console.print(f"[dim]Client ID: {client._client_id.decode()}[/dim]")
        # flags 是 ConnectFlags 对象，用属性访问
        session_present = flags.session_present if hasattr(flags, 'session_present') else False
        console.print(f"[dim]Session Present: {session_present}[/dim]")
    else:
        error_messages = {
            1: "连接被拒绝 - 协议版本不正确",
            2: "连接被拒绝 - 客户端 ID 无效",
            3: "连接被拒绝 - 服务器不可用",
            4: "连接被拒绝 - 用户名或密码错误",
            5: "连接被拒绝 - 未授权",
            128: "未指定错误",
            129: "格式错误的数据包",
            130: "协议错误",
            131: "实现特定错误",
            132: "不支持的协议版本",
            133: "客户端标识符无效",
            134: "用户名或密码错误",
            135: "未授权",
            136: "服务器不可用",
            137: "服务器繁忙",
            138: "禁止",
        }
        error_msg = error_messages.get(rc, f"错误代码: {rc}")
        console.print(f"[bold red]✗ 连接失败: {error_msg}[/bold red]")


def on_disconnect(client, userdata, flags, reason_code, properties):
    """断开连接回调（MQTT v5）"""
    rc = reason_code.value if hasattr(reason_code, 'value') else reason_code
    if rc == 0:
        console.print("[yellow]正常断开连接[/yellow]")
    else:
        console.print(f"[red]意外断开连接，代码: {rc}[/red]")


def on_message(client, userdata, msg):
    """消息回调"""
    console.print(f"[cyan]收到消息:[/cyan] {msg.topic}")
    console.print(f"[dim]{msg.payload.decode()}[/dim]")


def main():
    # 连接参数
    broker = "grve.me"
    port = 1883
    username = "dji"
    password = "lab605605"
    client_id = "test-client-python"

    console.print(Panel.fit(
        "[bold cyan]MQTT 连接测试[/bold cyan]\n"
        f"[dim]Broker: {broker}:{port}[/dim]\n"
        f"[dim]Username: {username}[/dim]\n"
        f"[dim]Client ID: {client_id}[/dim]",
        border_style="cyan"
    ))

    # 创建客户端
    console.print("\n[cyan]正在创建 MQTT 客户端...[/cyan]")
    client = mqtt.Client(
        client_id=client_id,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,  # 使用新版回调 API
        protocol=mqtt.MQTTv5  # 使用 MQTT 5.0
    )

    # 设置用户名和密码
    client.username_pw_set(username, password)

    # 设置回调
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # 尝试连接
    console.print(f"[cyan]正在连接到 {broker}:{port}...[/cyan]")

    try:
        client.connect(broker, port, keepalive=60)

        # 启动网络循环
        client.loop_start()

        # 等待连接建立
        console.print("[yellow]等待连接响应...[/yellow]")
        time.sleep(2)

        # 如果连接成功，订阅测试主题
        if client.is_connected():
            test_topic = "test/python/hello"
            console.print(f"\n[cyan]订阅测试主题: {test_topic}[/cyan]")
            client.subscribe(test_topic, qos=1)

            # 发布测试消息
            console.print(f"[cyan]发布测试消息...[/cyan]")
            client.publish(test_topic, "Hello from Python MQTT test!", qos=1)

            # 等待消息
            console.print("[yellow]等待消息回显（5秒）...[/yellow]")
            time.sleep(5)

            console.print("\n[bold green]✓ 测试完成！连接正常工作[/bold green]")
        else:
            console.print("\n[bold red]✗ 连接失败，请检查网络和凭据[/bold red]")

        # 断开连接
        console.print("\n[cyan]断开连接...[/cyan]")
        client.loop_stop()
        client.disconnect()

    except Exception as e:
        console.print(f"\n[bold red]✗ 发生错误: {e}[/bold red]")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())

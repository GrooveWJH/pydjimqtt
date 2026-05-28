from __future__ import annotations

import json
import time
from concurrent.futures import Future
from typing import Any


def publish(client, method: str, data: dict[str, Any], tid: str, console) -> Future:
    topic = f"thing/product/{client.gateway_sn}/services"
    payload = {
        "tid": tid,
        "bid": tid,
        "timestamp": int(time.time() * 1000),
        "method": method,
        "data": data,
    }
    future = Future()
    with client.lock:
        client.pending_requests[tid] = future

    if client.client is None:
        raise RuntimeError("MQTT client is not connected")
    client.client.publish(topic, json.dumps(payload), qos=1)
    console.print(f"[blue]→[/blue] 发送 {method} (tid: {tid[:8]}...)")
    return future

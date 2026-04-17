from __future__ import annotations

import json
from types import SimpleNamespace

from pydjimqtt.services import drc_commands


class _FakePahoClient:
    def __init__(self) -> None:
        self.on_message = None

    def publish(self, _topic: str, _payload: str, qos: int = 0) -> None:
        assert qos == 0
        return


class _FakeMQTTClient:
    def __init__(self) -> None:
        self.client = _FakePahoClient()


def test_take_photo_wait_returns_request_payload_index(monkeypatch) -> None:
    mqtt_client = _FakeMQTTClient()

    def _fake_take_photo(*args, **kwargs) -> None:
        assert kwargs["payload_index"] == "89-0-0"
        response_payload = {
            "method": "drc_camera_photo_take",
            "seq": kwargs["seq"],
            "timestamp": 1776414002533,
            "data": {"result": 0},
        }
        msg = SimpleNamespace(payload=json.dumps(response_payload).encode("utf-8"))
        mqtt_client.client.on_message(None, None, msg)

    monkeypatch.setattr(drc_commands, "take_photo", _fake_take_photo)

    result = drc_commands.take_photo_wait(
        mqtt_client,
        payload_index="89-0-0",
        timeout=0.1,
        seq=1179935,
    )

    assert result["ok"] is True
    assert result["payload_index"] == "89-0-0"
    assert result["raw"]["timestamp"] == 1776414002533

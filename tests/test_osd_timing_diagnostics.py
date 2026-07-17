from __future__ import annotations

import json
import threading
from types import SimpleNamespace

import pytest

from pydjimqtt.core import client_views, message_handlers
from pydjimqtt.core.state import initialize_client_state


class _Client:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        initialize_client_state(self, object)


def _handle_drc_message(client: _Client, payload: dict) -> None:
    message = SimpleNamespace(
        topic="thing/product/test/drc/up",
        payload=json.dumps(payload).encode("utf-8"),
    )
    message_handlers.handle_message(client, message, console=None)


def test_osd_timing_diagnostics_track_arrival_gap_and_sequence_loss(monkeypatch) -> None:
    clock = {"wall": 100.0, "monotonic": 10.0}
    monkeypatch.setattr(message_handlers.time, "time", lambda: clock["wall"])
    monkeypatch.setattr(message_handlers.time, "monotonic", lambda: clock["monotonic"])
    client = _Client()

    _handle_drc_message(
        client,
        {"method": "osd_info_push", "seq": 40, "data": {"height": 1.0}},
    )
    clock.update(wall=100.35, monotonic=10.35)
    _handle_drc_message(
        client,
        {"method": "osd_info_push", "seq": 43, "data": {"height": 1.1}},
    )

    diagnostics = client_views.get_osd_timing_diagnostics(client)

    assert diagnostics["window_samples"] == 1
    assert diagnostics["gap_p95_sec"] == pytest.approx(0.35)
    assert diagnostics["gap_max_sec"] == pytest.approx(0.35)
    assert diagnostics["drc_message_count"] == 2
    assert diagnostics["last_drc_message_monotonic"] == pytest.approx(10.35)
    assert diagnostics["drc_last_sequence"] == 43
    assert diagnostics["drc_sequence_discontinuities"] == 1
    assert diagnostics["drc_sequence_missing_total"] == 2

    clock["wall"] = 103.0
    assert client_views.get_osd_frequency(client) == 0.0


def test_drc_control_reply_does_not_break_telemetry_sequence(monkeypatch) -> None:
    clock = {"wall": 100.0, "monotonic": 10.0}
    monkeypatch.setattr(message_handlers.time, "time", lambda: clock["wall"])
    monkeypatch.setattr(message_handlers.time, "monotonic", lambda: clock["monotonic"])
    client = _Client()

    _handle_drc_message(
        client,
        {"method": "osd_info_push", "seq": 40, "data": {}},
    )
    clock.update(wall=100.1, monotonic=10.1)
    _handle_drc_message(
        client,
        {"method": "drc_camera_photo_take", "seq": 900_000, "data": {"result": 0}},
    )
    clock.update(wall=100.2, monotonic=10.2)
    _handle_drc_message(
        client,
        {"method": "hsi_info_push", "seq": 41, "data": {}},
    )

    diagnostics = client_views.get_osd_timing_diagnostics(client)

    assert diagnostics["drc_message_count"] == 3
    assert diagnostics["drc_last_sequence"] == 41
    assert diagnostics["drc_sequence_discontinuities"] == 0
    assert diagnostics["drc_sequence_missing_total"] == 0

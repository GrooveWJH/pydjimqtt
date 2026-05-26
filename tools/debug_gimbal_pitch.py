#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time
from argparse import ArgumentParser, Namespace
from dataclasses import replace

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from rich.console import Console
from rich.table import Table

from pydjimqtt import (
    DEFAULT_GIMBAL_PITCH_PROFILE,
    GimbalPitchStatus,
    MQTTClient,
    load_gimbal_pitch_profile,
    set_gimbal_pitch_async,
)


console = Console()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _parser() -> ArgumentParser:
    parser = ArgumentParser(description="Debug DJI gimbal pitch async control.")
    parser.add_argument("--target", type=float, required=True, help="Target pitch in degrees.")
    parser.add_argument("--host", default=_env("DJI_MQTT_HOST"), help="MQTT host.")
    parser.add_argument("--port", type=int, default=int(_env("DJI_MQTT_PORT", "1883")))
    parser.add_argument("--username", default=_env("DJI_MQTT_USERNAME", ""))
    parser.add_argument("--password", default=_env("DJI_MQTT_PASSWORD", ""))
    parser.add_argument("--gateway-sn", default=_env("DJI_GATEWAY_SN", ""))
    parser.add_argument("--payload-index", default=_env("DJI_PAYLOAD_INDEX", ""))
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--osd-timeout", type=float, default=10.0)
    parser.add_argument("--poll", type=float, default=0.25)
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use a low-latency debug profile and do not pad to the fixed deadline.",
    )
    parser.add_argument(
        "--no-profile",
        action="store_true",
        help="Ignore saved gateway-specific calibration profile.",
    )
    return parser


def _connect(args: Namespace) -> MQTTClient:
    if not args.host:
        raise SystemExit("--host or DJI_MQTT_HOST is required")
    if not args.gateway_sn:
        raise SystemExit("--gateway-sn or DJI_GATEWAY_SN is required")
    client = MQTTClient(
        gateway_sn=args.gateway_sn,
        mqtt_config={
            "host": args.host,
            "port": args.port,
            "username": args.username,
            "password": args.password,
        },
    )
    client.connect()
    return client


def _print_snapshot(client: MQTTClient, target: float, status: str) -> None:
    pitch, roll, yaw = client.get_gimbal_attitude()
    table = Table(title="Gimbal pitch debug")
    table.add_column("field")
    table.add_column("value")
    table.add_row("status", status)
    table.add_row("target_pitch", f"{target:.2f}")
    table.add_row("current_pitch", "None" if pitch is None else f"{float(pitch):.2f}")
    table.add_row("roll", "None" if roll is None else f"{float(roll):.2f}")
    table.add_row("yaw", "None" if yaw is None else f"{float(yaw):.2f}")
    console.print(table)


def _print_trace(result) -> None:
    if not result.trace:
        return
    table = Table(title="Gimbal pitch control trace")
    table.add_column("step", justify="right")
    table.add_column("speed", justify="right")
    table.add_column("start", justify="right")
    table.add_column("end", justify="right")
    table.add_column("progress", justify="right")
    table.add_column("duration_s", justify="right")
    table.add_column("stopped")
    for step in result.trace:
        table.add_row(
            str(step.index),
            f"{step.commanded_speed:.2f}",
            f"{step.start_pitch:.2f}",
            f"{step.end_pitch:.2f}",
            f"{step.progress_deg:.2f}",
            f"{step.duration_s:.3f}",
            str(step.stopped),
        )
    console.print(table)


def _wait_until_gimbal_osd_ready(client: MQTTClient, args: Namespace) -> str | None:
    console.print(
        f"[yellow]Waiting for camera OSD and gimbal attitude "
        f"(timeout={args.osd_timeout:.1f}s)...[/yellow]"
    )
    pitch, roll, yaw = client.wait_for_gimbal_attitude(
        timeout=args.osd_timeout,
        poll_interval=args.poll,
    )
    payload_index = args.payload_index or client.get_payload_index()
    console.print(
        "[green]Camera OSD ready[/green] "
        f"payload_index={payload_index or 'None'} "
        f"pitch={pitch:.2f} roll={roll:.2f} yaw={yaw:.2f}"
    )
    return payload_index or None


def _profile_from_args(args: Namespace):
    gateway_sn = getattr(args, "gateway_sn", "")
    if gateway_sn and not getattr(args, "no_profile", False):
        profile = load_gimbal_pitch_profile(gateway_sn)
        if profile is not None:
            return profile, None
    if not args.fast:
        return DEFAULT_GIMBAL_PITCH_PROFILE, None
    return (
        replace(
            DEFAULT_GIMBAL_PITCH_PROFILE,
            settle_seconds=0.04,
            proportional_gain=2.0,
            max_speed=40.0,
            confirm_reads=4,
            max_control_iterations=50,
            observation_window_s=0.22,
            control_interval_s=0.08,
            stall_timeout_s=1.2,
            pad_to_deadline=False,
            deadline_s=0.0,
        ),
        False,
    )


def main() -> int:
    args = _parser().parse_args()
    client = _connect(args)
    try:
        payload_index = _wait_until_gimbal_osd_ready(client, args)
        profile, pad_to_deadline = _profile_from_args(args)
        task = set_gimbal_pitch_async(
            client,
            args.target,
            profile=profile,
            payload_index=payload_index,
            pad_to_deadline=pad_to_deadline,
        )
        deadline = time.monotonic() + max(0.1, args.timeout)
        while not task.done() and time.monotonic() < deadline:
            _print_snapshot(client, args.target, str(task.status()))
            time.sleep(max(0.05, args.poll))
        result = task.result(timeout=max(0.1, deadline - time.monotonic()))
        _print_snapshot(client, args.target, str(result.status))
        _print_trace(result)
        console.print(result)
        return 0 if result.status == GimbalPitchStatus.SUCCEEDED else 2
    finally:
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())

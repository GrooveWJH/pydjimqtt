#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from argparse import ArgumentParser, Namespace
from dataclasses import asdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

from rich.console import Console
from rich.table import Table

from pydjimqtt import MQTTClient, save_gimbal_pitch_profile
from pydjimqtt.gimbal.calibration import calibrate_gimbal_pitch


console = Console()


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _parser() -> ArgumentParser:
    parser = ArgumentParser(description="Calibrate DJI gimbal pitch control profile.")
    parser.add_argument("--host", default=_env("DJI_MQTT_HOST"), help="MQTT host.")
    parser.add_argument("--port", type=int, default=int(_env("DJI_MQTT_PORT", "1883")))
    parser.add_argument("--username", default=_env("DJI_MQTT_USERNAME", ""))
    parser.add_argument("--password", default=_env("DJI_MQTT_PASSWORD", ""))
    parser.add_argument("--gateway-sn", default=_env("DJI_GATEWAY_SN", ""))
    parser.add_argument("--payload-index", default=_env("DJI_PAYLOAD_INDEX", ""))
    parser.add_argument("--osd-timeout", type=float, default=10.0)
    parser.add_argument("--yes", action="store_true", help="Allow full-range gimbal motion.")
    return parser


def _ensure_confirmed(args: Namespace) -> bool:
    if args.yes:
        return True
    console.print(
        "[red]Calibration moves the gimbal through a wide pitch range.[/red] "
        "Re-run with --yes to start."
    )
    return False


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


def _print_result(result) -> None:
    summary = Table(title="Gimbal Pitch Calibration Summary")
    summary.add_column("field")
    summary.add_column("value")
    summary.add_row("status", str(result.status))
    summary.add_row("physical_min", f"{result.physical_min:.2f}")
    summary.add_row("physical_max", f"{result.physical_max:.2f}")
    summary.add_row("lower_limit_confirmed", str(result.reached_lower_limit))
    summary.add_row("upper_limit_confirmed", str(result.reached_upper_limit))
    summary.add_row("elapsed_s", f"{result.elapsed_s:.3f}")
    if result.error:
        summary.add_row("error", result.error)
    console.print(summary)

    profile = result.profile
    params = Table(title="Recommended Profile")
    params.add_column("parameter")
    params.add_column("value")
    for name in (
        "proportional_gain",
        "min_speed",
        "max_speed",
        "near_target_speed",
        "near_target_error_deg",
        "settle_tolerance_deg",
        "settle_seconds",
        "confirm_reads",
        "max_control_iterations",
        "observation_window_s",
        "control_interval_s",
        "stall_timeout_s",
    ):
        params.add_row(name, str(getattr(profile, name)))
    console.print(params)

    samples = Table(title="Calibration Samples")
    samples.add_column("direction")
    samples.add_column("speed")
    samples.add_column("duration_s")
    samples.add_column("start")
    samples.add_column("end")
    samples.add_column("velocity/speed")
    for sample in result.samples:
        samples.add_row(
            sample.direction,
            f"{sample.speed:.2f}",
            f"{sample.duration_s:.3f}",
            f"{sample.start_pitch:.2f}",
            f"{sample.end_pitch:.2f}",
            f"{sample.velocity_per_speed:.3f}",
        )
    console.print(samples)


def main() -> int:
    args = _parser().parse_args()
    if not _ensure_confirmed(args):
        return 2
    client = _connect(args)
    try:
        client.wait_for_gimbal_attitude(timeout=args.osd_timeout, poll_interval=0.1)
        payload_index = args.payload_index or client.get_payload_index()
        if not payload_index:
            raise SystemExit("camera payload_index is not available from OSD")
        result = calibrate_gimbal_pitch(client, payload_index=payload_index)
        _print_result(result)
        saved = save_gimbal_pitch_profile(
            args.gateway_sn,
            result.profile,
            metadata={
                "physical_min": result.physical_min,
                "physical_max": result.physical_max,
                "reached_lower_limit": result.reached_lower_limit,
                "reached_upper_limit": result.reached_upper_limit,
                "samples": [asdict(sample) for sample in result.samples],
                "status": str(result.status),
            },
        )
        console.print(f"[green]Saved profile:[/green] {saved}")
        return 0 if str(result.status) == "SUCCEEDED" else 2
    finally:
        client.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())

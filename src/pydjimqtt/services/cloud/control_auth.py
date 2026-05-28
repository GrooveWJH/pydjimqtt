from __future__ import annotations

from ...core import ServiceCaller
from ..common import call_service, console


def request_control_auth(
    caller: ServiceCaller,
    user_id: str = "default_user",
    user_callsign: str = "Cloud Pilot",
) -> dict:
    """请求控制权"""
    console.print("[bold cyan]请求控制权...[/bold cyan]")
    return call_service(
        caller,
        "cloud_control_auth_request",
        {
            "user_id": user_id,
            "user_callsign": user_callsign,
            "control_keys": ["flight"],
        },
        "控制权请求成功",
    )


def release_control_auth(caller: ServiceCaller) -> dict:
    """释放控制权"""
    console.print("[cyan]释放控制权...[/cyan]")
    return call_service(caller, "cloud_control_auth_release", success_msg="控制权已释放")

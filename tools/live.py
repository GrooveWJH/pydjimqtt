#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

tool_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, tool_dir)
sys.path.insert(0, os.path.dirname(tool_dir))

from live_cli.main import console, main


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        console.print(f"\n[bold red]程序异常: {exc}[/bold red]")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")

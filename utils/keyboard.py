#!/usr/bin/env python3
"""Virtual joystick keyboard tester compatibility entrypoint."""

try:
    from .keyboard_app import JoystickApp
except ImportError:  # pragma: no cover - direct script execution
    from keyboard_app import JoystickApp


def main() -> None:
    app = JoystickApp(scale=1.0)
    app.run()


if __name__ == "__main__":
    main()

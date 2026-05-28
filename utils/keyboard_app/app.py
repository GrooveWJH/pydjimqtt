"""Textual application for the virtual joystick keyboard tester."""

import threading
from collections.abc import Callable

from pynput import keyboard
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.widgets import Static

from .constants import FULL_RANGE, HALF_RANGE, NEUTRAL
from .widgets import ControlsWidget, JoystickWidget, KeyStatusWidget


class JoystickApp(App):
    """Virtual joystick test app."""

    CSS = """
    Screen {
        align: center middle;
    }

    #window_container {
        width: 92%;
        height: 92%;
        padding: 1 2;
    }

    #window_title {
        height: 3;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }

    #joysticks_section {
        height: auto;
        padding: 0;
        margin-bottom: 1;
    }

    #joysticks {
        height: auto;
    }

    #controls_section {
        height: auto;
        padding: 0;
        margin-bottom: 1;
    }

    #status_section {
        height: auto;
        padding: 0;
    }

    JoystickWidget {
        width: 1fr;
        height: auto;
    }

    ControlsWidget {
        width: 100%;
        height: auto;
    }

    KeyStatusWidget {
        width: 100%;
        height: auto;
    }
    """

    TITLE = "🎮 虚拟摇杆测试工具（美国手模式）"
    BINDINGS = [("ctrl+c", "quit", "退出")]

    paused = reactive(False)
    pressed_keys = reactive(set())

    stick_state = {
        "throttle": NEUTRAL,
        "yaw": NEUTRAL,
        "pitch": NEUTRAL,
        "roll": NEUTRAL,
    }

    _pressed_keys_state = set()
    _state_lock = threading.Lock()
    _shift_pressed = False
    _keyboard_listener = None

    def __init__(
        self,
        scale: float = 1.0,
        on_stick_update: Callable[[dict[str, int]], None] | None = None,
        on_emergency_stop: Callable[[], None] | None = None,
        update_interval: float = 0.05,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.scale = scale
        self.on_stick_update = on_stick_update
        self.on_emergency_stop = on_emergency_stop
        self.update_interval = update_interval
        self._pressed_keys_state = set()
        self._state_lock = threading.Lock()
        self._shift_pressed = False
        self._keyboard_listener = None
        self._emergency_stop_armed = False

    def compose(self) -> ComposeResult:
        with Container(id="window_container"):
            yield Static(
                "[bold cyan]🎮 虚拟摇杆测试工具 (美国手模式)[/bold cyan]",
                id="window_title",
            )
            with Container(id="joysticks_section"):
                with Horizontal(id="joysticks"):
                    self.left_joystick = JoystickWidget(
                        "🕹️  左摇杆 (QE)",
                        "偏航 (Yaw)",
                        "油门 (Throttle)",
                        scale=self.scale,
                        id="left_joystick",
                    )
                    yield self.left_joystick
                    self.right_joystick = JoystickWidget(
                        "🕹️  右摇杆 (WASD)",
                        "横滚 (Roll)",
                        "俯仰 (Pitch)",
                        scale=self.scale,
                        id="right_joystick",
                    )
                    yield self.right_joystick
            with Container(id="controls_section"):
                yield ControlsWidget(id="controls")
            with Container(id="status_section"):
                self.key_status = KeyStatusWidget(id="key_status")
                yield self.key_status

    def on_mount(self) -> None:
        self.set_interval(self.update_interval, self.update_sticks)
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press, on_release=self._on_key_release
        )
        self._keyboard_listener.start()

    def on_unmount(self) -> None:
        listener = self._keyboard_listener
        if listener:
            listener.stop()
            try:
                listener.join(timeout=1.0)
            except RuntimeError:
                pass
            finally:
                self._keyboard_listener = None
        self._pressed_keys_state.clear()

    def _normalize_key(self, key):
        try:
            key_char = key.char.lower() if hasattr(key, "char") else None
        except AttributeError:
            key_char = None

        key_map = {
            keyboard.Key.space: "space",
            keyboard.Key.shift: "shift",
            keyboard.Key.shift_r: "shift",
        }
        is_shift = key in (keyboard.Key.shift, keyboard.Key.shift_r)
        return key_map.get(key, key_char), is_shift

    def _toggle_pause_ui(self) -> None:
        new_state = not self.paused
        self.paused = new_state
        self.key_status.paused = new_state

        if new_state:
            self.title = "🎮 虚拟摇杆 - ⏸️  已暂停"
            with self._state_lock:
                self._pressed_keys_state.clear()
            self.pressed_keys = set()
            self.key_status.pressed_keys = set()
        else:
            self.title = "🎮 虚拟摇杆测试工具（美国手模式）"

    def _on_key_press(self, key) -> None:
        key_char, is_shift = self._normalize_key(key)

        if key_char == "b":
            if self.on_emergency_stop and not self.paused and not self._emergency_stop_armed:
                self._emergency_stop_armed = True
                self.call_from_thread(self.on_emergency_stop)
            return

        with self._state_lock:
            if key_char:
                self._pressed_keys_state.add(key_char)

        if is_shift:
            self._shift_pressed = True
        if key_char == "p":
            self.call_from_thread(self._toggle_pause_ui)

    def _on_key_release(self, key) -> None:
        key_char, is_shift = self._normalize_key(key)

        if key_char == "b":
            self._emergency_stop_armed = False
            return

        with self._state_lock:
            if key_char:
                self._pressed_keys_state.discard(key_char)

        if is_shift:
            self._shift_pressed = False

    def reset_sticks(self) -> None:
        self.stick_state["throttle"] = NEUTRAL
        self.stick_state["yaw"] = NEUTRAL
        self.stick_state["pitch"] = NEUTRAL
        self.stick_state["roll"] = NEUTRAL

    def update_sticks(self) -> None:
        self.reset_sticks()

        if self.paused:
            self.pressed_keys = set()
            self.key_status.pressed_keys = set()
            return

        with self._state_lock:
            current_keys = self._pressed_keys_state.copy()

        self.pressed_keys = current_keys
        self.key_status.pressed_keys = current_keys

        key_mappings = {
            "w": ("pitch", HALF_RANGE),
            "s": ("pitch", -HALF_RANGE),
            "a": ("roll", -HALF_RANGE),
            "d": ("roll", HALF_RANGE),
            "q": ("yaw", -HALF_RANGE),
            "e": ("yaw", HALF_RANGE),
            "space": ("throttle", HALF_RANGE),
        }
        for key, (channel, delta) in key_mappings.items():
            if key in current_keys:
                self.stick_state[channel] = NEUTRAL + delta

        shift_pressed = "shift" in current_keys or any(
            "shift" in key.lower() for key in current_keys if isinstance(key, str)
        )
        if shift_pressed:
            self.stick_state["throttle"] = NEUTRAL - FULL_RANGE
        elif "k" in current_keys:
            self.stick_state["throttle"] = NEUTRAL - FULL_RANGE
            self.stick_state["yaw"] = NEUTRAL - FULL_RANGE
            self.stick_state["pitch"] = NEUTRAL - FULL_RANGE
            self.stick_state["roll"] = NEUTRAL + FULL_RANGE

        self.left_joystick.update_values(self.stick_state["yaw"], self.stick_state["throttle"])
        self.right_joystick.update_values(self.stick_state["roll"], self.stick_state["pitch"])

        if self.on_stick_update and current_keys:
            self.on_stick_update(self.stick_state)

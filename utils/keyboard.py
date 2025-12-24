#!/usr/bin/env python3
"""
键盘控制测试工具 - 虚拟摇杆可视化（美国手模式）

功能：
- 在 TUI 中实时显示两个虚拟摇杆
- 根据键盘输入实时更新摇杆位置
- 显示杆量数值（364-1684，中值1024）
- 零延迟按键检测（真正的按下/释放事件）

按键说明：
- W/S: 俯仰 前↑/后↓
- A/D: 横滚 左←/右→
- Q/E: 偏航 左←/右→
- 空格: 上升 (半杆量)
- Shift: 下降 (满杆量)
- K 键: 外八解锁（左下右下，用于解锁无人机）
- P: 暂停/恢复
- Ctrl+C：退出

⚠️ 安全机制：
- 零延迟响应：松开按键立即停止（pynput 真实按键事件）
- 手动暂停：P 快捷键
- 被动监听：不拦截按键，不干扰其他程序
"""
import threading
from pynput import keyboard

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Static
from textual.reactive import reactive
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.text import Text

# 杆量常量
NEUTRAL = 1024
HALF_RANGE = 330
FULL_RANGE = 660
MIN_VALUE = 364
MAX_VALUE = 1684


class JoystickWidget(Static):
    """虚拟摇杆组件"""

    def __init__(self, title: str, x_label: str, y_label: str, scale: float = 1.0, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.x_label = x_label
        self.y_label = y_label
        self.scale = scale
        self.x_value = NEUTRAL
        self.y_value = NEUTRAL

    def update_values(self, x_value: int, y_value: int):
        """更新摇杆值"""
        self.x_value = x_value
        self.y_value = y_value
        self.refresh()

    def _get_cell_style(self, x: int, y: int, x_pos: int, y_pos: int, x_percent: float, y_percent: float, size: int):
        """Determine character and style for a joystick cell.

        Returns: (char, style)
        """
        dist_from_center = (x**2 + y**2) ** 0.5

        # Joystick position (3x3 area)
        if abs(x - x_pos) <= 1 and abs(y - y_pos) <= 1:
            offset_mag = (x_percent**2 + y_percent**2) ** 0.5
            is_positive = x_percent > 0 or y_percent > 0

            if offset_mag < 10:
                return "●", "bold yellow"
            elif offset_mag < 50:
                return "◆", "bold green" if is_positive else "bold red"
            else:
                return "█", "bold bright_green" if is_positive else "bold bright_red"

        # Circle boundary
        if abs(dist_from_center - size) < 0.8:
            return "◯", "dim blue"

        # Center crosshair
        if x == 0 and y == 0:
            return "┼", "dim white"
        elif x == 0:
            return "│", "dim white"
        elif y == 0:
            return "─", "dim white"

        return " ", ""

    @staticmethod
    def _get_diff_color(diff: int) -> str:
        """Get color based on difference from neutral."""
        return "green" if diff > 0 else "red" if diff < 0 else "yellow"

    def render(self):
        """渲染摇杆"""
        size = int(10 * self.scale)
        x_percent = ((self.x_value - NEUTRAL) / FULL_RANGE) * 100
        y_percent = ((self.y_value - NEUTRAL) / FULL_RANGE) * 100

        x_pos = int((x_percent / 100) * size)
        y_pos = int((y_percent / 100) * size)

        # 构建摇杆可视化
        from rich.console import Group

        lines = []
        for y in range(size, -size - 1, -1):
            line_text = Text()
            for x in range(-size, size + 1):
                char, style = self._get_cell_style(
                    x, y, x_pos, y_pos, x_percent, y_percent, size)
                line_text.append(char, style=style if style else None)
            lines.append(line_text)

        joystick_display = Group(*lines)

        # 数值显示
        x_diff = self.x_value - NEUTRAL
        y_diff = self.y_value - NEUTRAL

        x_color = self._get_diff_color(x_diff)
        y_color = self._get_diff_color(y_diff)

        # 组合内容
        content = Group(
            Align.center(joystick_display, vertical="middle"),
            "",
            Align.center(Text(
                f"{self.x_label}: {self.x_value:4d} ({x_diff:+4d}) {x_percent:+6.1f}%", style=x_color)),
            Align.center(Text(
                f"{self.y_label}: {self.y_value:4d} ({y_diff:+4d}) {y_percent:+6.1f}%", style=y_color))
        )

        return Panel(
            content,
            title=f"[bold cyan]{self.title}[/bold cyan]",
            border_style="cyan",
        )


class ControlsWidget(Static):
    """控制说明组件"""

    def render(self):
        table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
        table.add_column("按键", style="cyan bold", width=10)
        table.add_column("功能", style="white", width=22)

        table.add_row("W / S", "俯仰 前↑/后↓")
        table.add_row("A / D", "横滚 左←/右→")
        table.add_row("Q / E", "偏航 左←/右→")
        table.add_row("空格", "上升 (半杆量)")
        table.add_row("Shift", "下降 (满杆量)")
        table.add_row("K", "外八解锁")
        table.add_row("P", "暂停/恢复")
        table.add_row("Ctrl+C", "退出")

        return Panel(
            table,
            title="[bold cyan]🎮 控制说明[/bold cyan]",
            border_style="cyan"
        )


class KeyStatusWidget(Static):
    """按键状态组件"""

    pressed_keys = reactive(set())
    paused = reactive(False)

    def render(self):
        if self.paused:
            content = Text("⏸️  已暂停（按 P 恢复）", style="bold black on yellow")
        elif self.pressed_keys:
            keys_text = ", ".join(sorted(self.pressed_keys))
            content = Text(keys_text, style="green bold")
        else:
            content = Text("无按键", style="dim")

        return Panel(
            Align.center(content, vertical="middle"),
            title="[bold cyan]⌨️  当前按键[/bold cyan]",
            border_style="cyan"
        )


class JoystickApp(App):
    """虚拟摇杆测试工具"""

    CSS = """
    Screen {
        align: center middle;
    }

    #window_container {
        width: 90%;
        height: 90%;
        border: round cyan;
        padding: 1 2;
    }

    #window_title {
        height: 3;
        width: 100%;
        border: solid cyan;
        content-align: center middle;
        margin-bottom: 1;
    }

    #joysticks_section {
        height: auto;
        border: solid green;
        padding: 1;
        margin-bottom: 1;
    }

    #joysticks {
        height: auto;
    }

    #controls_section {
        height: auto;
        border: solid yellow;
        padding: 1;
        margin-bottom: 1;
    }

    #status_section {
        height: auto;
        border: solid magenta;
        padding: 1;
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

    # 禁用默认的 Ctrl+Q 退出，改用 Ctrl+C
    BINDINGS = [
        ("ctrl+c", "quit", "退出"),
    ]

    # 响应式状态
    paused = reactive(False)  # 手动暂停
    pressed_keys = reactive(set())

    # 摇杆状态
    stick_state = {
        'throttle': NEUTRAL,
        'yaw': NEUTRAL,
        'pitch': NEUTRAL,
        'roll': NEUTRAL,
    }

    # 按键状态（pynput 监听）
    _pressed_keys_state = set()  # 真实按键状态
    _state_lock = threading.Lock()  # 线程安全
    _shift_pressed = False  # Shift 键状态
    _keyboard_listener = None  # pynput 监听器

    def __init__(self, scale: float = 1.0, on_stick_update=None, update_interval=0.05, **kwargs):
        super().__init__(**kwargs)
        self.scale = scale
        self.on_stick_update = on_stick_update  # 可选回调：当摇杆值更新时调用
        self.update_interval = update_interval  # 更新间隔（秒）
        self._pressed_keys_state = set()
        self._state_lock = threading.Lock()
        self._shift_pressed = False
        self._keyboard_listener = None

    def compose(self) -> ComposeResult:
        """组合 UI 组件 - 窗口风格布局"""
        with Container(id="window_container"):
            # 窗口标题栏
            yield Static(
                "[bold cyan]🎮 虚拟摇杆测试工具 (美国手模式)[/bold cyan]",
                id="window_title"
            )

            # 摇杆区域（绿色边框）
            with Container(id="joysticks_section"):
                with Horizontal(id="joysticks"):
                    self.left_joystick = JoystickWidget(
                        "🕹️  左摇杆 (QE)",
                        "偏航 (Yaw)",
                        "油门 (Throttle)",
                        scale=self.scale,
                        id="left_joystick"
                    )
                    yield self.left_joystick

                    self.right_joystick = JoystickWidget(
                        "🕹️  右摇杆 (WASD)",
                        "横滚 (Roll)",
                        "俯仰 (Pitch)",
                        scale=self.scale,
                        id="right_joystick"
                    )
                    yield self.right_joystick

            # 控制说明区域（黄色边框）
            with Container(id="controls_section"):
                yield ControlsWidget(id="controls")

            # 按键状态区域（红色边框）
            with Container(id="status_section"):
                self.key_status = KeyStatusWidget(id="key_status")
                yield self.key_status

    def on_mount(self) -> None:
        """启动时设置定时刷新和键盘监听"""
        self.set_interval(self.update_interval, self.update_sticks)

        # 启动 pynput 键盘监听（后台线程）
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self._keyboard_listener.start()

    def on_unmount(self) -> None:
        """退出时清理资源"""
        listener = self._keyboard_listener
        if listener:
            listener.stop()
            try:
                # Ensure the background listener thread releases resources promptly
                listener.join(timeout=1.0)
            except RuntimeError:
                pass
            finally:
                self._keyboard_listener = None
        self._pressed_keys_state.clear()

    def _normalize_key(self, key):
        """Convert pynput key to normalized string.

        Returns: (key_char, is_shift)
        """
        try:
            key_char = key.char.lower() if hasattr(key, 'char') else None
        except AttributeError:
            key_char = None

        # Map special keys
        key_map = {
            keyboard.Key.space: 'space',
            keyboard.Key.shift: 'shift',
            keyboard.Key.shift_r: 'shift',
        }

        is_shift = key in (keyboard.Key.shift, keyboard.Key.shift_r)
        return key_map.get(key, key_char), is_shift

    def _toggle_pause_ui(self) -> None:
        """在 Textual 主线程上切换暂停状态并刷新界面。"""
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

    def _on_key_press(self, key):
        """pynput 按键按下事件（后台线程）"""
        key_char, is_shift = self._normalize_key(key)

        with self._state_lock:
            if key_char:
                self._pressed_keys_state.add(key_char)

        if is_shift:
            self._shift_pressed = True

        # P 键：切换手动暂停（无需 Shift）
        if key_char == 'p':
            self.call_from_thread(self._toggle_pause_ui)
            return

    def _on_key_release(self, key):
        """pynput 按键释放事件（后台线程）- 零延迟"""
        key_char, is_shift = self._normalize_key(key)

        with self._state_lock:
            if key_char:
                self._pressed_keys_state.discard(key_char)

        if is_shift:
            self._shift_pressed = False

    def reset_sticks(self):
        """重置所有通道到中值"""
        self.stick_state['throttle'] = NEUTRAL
        self.stick_state['yaw'] = NEUTRAL
        self.stick_state['pitch'] = NEUTRAL
        self.stick_state['roll'] = NEUTRAL

    def update_sticks(self):
        """根据按下的按键更新杆量（优先级检查）"""
        # Always reset first (simpler flow)
        self.reset_sticks()

        # 手动暂停检查
        if self.paused:
            self.pressed_keys = set()
            self.key_status.pressed_keys = set()
            return

        # 获取当前按键状态（线程安全）
        with self._state_lock:
            current_keys = self._pressed_keys_state.copy()

        # 更新显示
        self.pressed_keys = current_keys
        self.key_status.pressed_keys = current_keys

        # Key-to-stick mapping (channel, delta)
        # WASD: 前后左右 (pitch, roll) - 半杆量
        # Q/E: 偏航 (yaw) - 半杆量
        # Space: 上升 (throttle) - 半杆量
        # Shift: 下降 (throttle) - 满杆量
        # K: 外八解锁
        key_mappings = {
            'w': ('pitch', HALF_RANGE),      # 前进
            's': ('pitch', -HALF_RANGE),     # 后退
            'a': ('roll', -HALF_RANGE),      # 左移
            'd': ('roll', HALF_RANGE),       # 右移
            'q': ('yaw', -HALF_RANGE),       # 左转
            'e': ('yaw', HALF_RANGE),        # 右转
            'space': ('throttle', HALF_RANGE),  # 上升
        }

        # Apply normal key mappings
        for key, (channel, delta) in key_mappings.items():
            if key in current_keys:
                self.stick_state[channel] = NEUTRAL + delta

        # Check if shift is pressed (check both normalized and raw keys)
        shift_pressed = ('shift' in current_keys or
                         any('shift' in k.lower() for k in current_keys if isinstance(k, str)))

        # Special commands override
        if shift_pressed:  # 下降 - 满杆量
            self.stick_state['throttle'] = NEUTRAL - FULL_RANGE
        elif 'k' in current_keys:  # Unlock pattern (外八解锁)
            self.stick_state['throttle'] = NEUTRAL - FULL_RANGE
            self.stick_state['yaw'] = NEUTRAL - FULL_RANGE
            self.stick_state['pitch'] = NEUTRAL - FULL_RANGE
            self.stick_state['roll'] = NEUTRAL + FULL_RANGE

        # 更新摇杆显示
        self.left_joystick.update_values(
            self.stick_state['yaw'],
            self.stick_state['throttle']
        )
        self.right_joystick.update_values(
            self.stick_state['roll'],
            self.stick_state['pitch']
        )

        # 如果有回调且未暂停，且有按键按下时，调用回调传递摇杆状态
        if self.on_stick_update and not self.paused and current_keys:
            self.on_stick_update(self.stick_state)


def main():
    # 运行 Textual App
    app = JoystickApp(scale=1.0)
    app.run()


if __name__ == '__main__':
    main()

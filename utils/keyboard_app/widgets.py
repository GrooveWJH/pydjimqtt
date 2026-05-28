"""Textual widgets used by the virtual joystick app."""

from rich.align import Align
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from .constants import FULL_RANGE, NEUTRAL


class JoystickWidget(Static):
    """Virtual joystick visualization."""

    def __init__(self, title: str, x_label: str, y_label: str, scale: float = 1.0, **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.x_label = x_label
        self.y_label = y_label
        self.scale = scale
        self.x_value = NEUTRAL
        self.y_value = NEUTRAL

    def update_values(self, x_value: int, y_value: int) -> None:
        self.x_value = x_value
        self.y_value = y_value
        self.refresh()

    def _get_cell_style(
        self,
        x: int,
        y: int,
        x_pos: int,
        y_pos: int,
        x_percent: float,
        y_percent: float,
        size: int,
    ) -> tuple[str, str]:
        dist_from_center = (x**2 + y**2) ** 0.5

        if abs(x - x_pos) <= 1 and abs(y - y_pos) <= 1:
            offset_mag = (x_percent**2 + y_percent**2) ** 0.5
            is_positive = x_percent > 0 or y_percent > 0
            if offset_mag < 10:
                return "●", "bold yellow"
            if offset_mag < 50:
                return "◆", "bold green" if is_positive else "bold red"
            return "█", "bold bright_green" if is_positive else "bold bright_red"

        if abs(dist_from_center - size) < 0.8:
            return "◯", "dim blue"
        if x == 0 and y == 0:
            return "┼", "dim white"
        if x == 0:
            return "│", "dim white"
        if y == 0:
            return "─", "dim white"
        return " ", ""

    @staticmethod
    def _get_diff_color(diff: int) -> str:
        return "green" if diff > 0 else "red" if diff < 0 else "yellow"

    def render(self):
        size = int(10 * self.scale)
        x_percent = ((self.x_value - NEUTRAL) / FULL_RANGE) * 100
        y_percent = ((self.y_value - NEUTRAL) / FULL_RANGE) * 100
        x_pos = int((x_percent / 100) * size)
        y_pos = int((y_percent / 100) * size)

        lines = []
        for y in range(size, -size - 1, -1):
            line_text = Text()
            for x in range(-size, size + 1):
                char, style = self._get_cell_style(x, y, x_pos, y_pos, x_percent, y_percent, size)
                line_text.append(char, style=style if style else None)
            lines.append(line_text)

        x_diff = self.x_value - NEUTRAL
        y_diff = self.y_value - NEUTRAL
        content = Group(
            Align.center(Group(*lines), vertical="middle"),
            "",
            Align.center(
                Text(
                    f"{self.x_label}: {self.x_value:4d} ({x_diff:+4d}) {x_percent:+6.1f}%",
                    style=self._get_diff_color(x_diff),
                )
            ),
            Align.center(
                Text(
                    f"{self.y_label}: {self.y_value:4d} ({y_diff:+4d}) {y_percent:+6.1f}%",
                    style=self._get_diff_color(y_diff),
                )
            ),
        )
        return Panel(content, title=f"[bold cyan]{self.title}[/bold cyan]", border_style="cyan")


class ControlsWidget(Static):
    """Keyboard control help."""

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
        table.add_row("B", "急停")
        table.add_row("P", "暂停/恢复")
        table.add_row("Ctrl+C", "退出")
        return Panel(table, title="[bold cyan]🎮 控制说明[/bold cyan]", border_style="cyan")


class KeyStatusWidget(Static):
    """Currently pressed key status."""

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
            border_style="cyan",
        )

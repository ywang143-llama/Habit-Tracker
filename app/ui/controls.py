"""Reusable custom widgets and window-dragging behavior."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from customtkinter import ScalingTracker

from . import theme


def ui_scale(widget) -> float:
    try:
        return float(ScalingTracker.get_widget_scaling(widget))
    except Exception:
        return 1.0


def ellipsize(text: str, font, max_width: float) -> str:
    """Trim *text* to fit, adding an ellipsis when needed."""
    if max_width <= 0:
        return ""
    try:
        if font.measure(text) <= max_width:
            return text
    except (tk.TclError, AttributeError):
        return text

    ellipsis = "\u2026"
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        candidate = text[:middle].rstrip() + ellipsis
        try:
            width = font.measure(candidate)
        except tk.TclError:
            return candidate
        if width <= max_width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + ellipsis


class CheckCircle(tk.Canvas):
    """A light circular checkbox with a hand-drawn check mark."""

    def __init__(
        self,
        master,
        *,
        checked: bool,
        command: Callable[[], None],
        bg_color: str,
        size: int = 22,
    ) -> None:
        self._scale = ui_scale(master)
        pixels = max(int(round(size * self._scale)), 14)
        super().__init__(
            master,
            width=pixels,
            height=pixels,
            bg=bg_color,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=1,
        )
        self._pixels = pixels
        self._checked = checked
        self._hovered = False
        self._command = command

        self.bind("<Button-1>", self._on_click)
        self.bind("<Return>", self._on_click)
        self.bind("<space>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._draw()

    def set_state(self, checked: bool) -> None:
        if checked == self._checked:
            return
        self._checked = checked
        self._draw()

    def set_background(self, color: str) -> None:
        self.configure(bg=color)

    def _on_click(self, _event=None) -> None:
        self._command()

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self.configure(cursor="hand2")
        self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        pixels = self._pixels
        pad = max(1.0, 1.6 * self._scale)
        width = max(1, round(1.5 * self._scale))
        inset = pad / 2

        if self._checked:
            self.create_oval(
                inset,
                inset,
                pixels - inset,
                pixels - inset,
                fill=theme.ACCENT,
                outline=theme.ACCENT,
            )
            self.create_line(
                pixels * 0.29,
                pixels * 0.53,
                pixels * 0.44,
                pixels * 0.68,
                pixels * 0.73,
                pixels * 0.35,
                fill=theme.ON_ACCENT,
                width=max(2, round(2.1 * self._scale)),
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
            )
        else:
            outline = theme.ACCENT if self._hovered else theme.FAINT
            self.create_oval(
                inset,
                inset,
                pixels - inset,
                pixels - inset,
                fill="",
                outline=outline,
                width=width,
            )


def mark_no_drag(widget):
    """Prevent a control (and its children) from starting a window drag."""
    try:
        widget._no_drag = True
    except Exception:
        pass
    return widget


def _inside_no_drag(widget, stop) -> bool:
    current = widget
    while current is not None:
        if getattr(current, "_no_drag", False):
            return True
        if current is stop:
            break
        current = getattr(current, "master", None)
    return False


def attach_drag(
    window, on_end: Optional[Callable[[int, int], None]] = None
) -> None:
    """Let the user drag a frameless window by its background.

    Controls marked with :func:`mark_no_drag` keep their normal behavior.
    """
    state = {"active": False, "dx": 0, "dy": 0, "moved": False, "x": 0, "y": 0}

    def start(event) -> None:
        if _inside_no_drag(event.widget, window):
            state["active"] = False
            return
        state["active"] = True
        state["moved"] = False
        state["dx"] = int(event.x_root) - window.winfo_x()
        state["dy"] = int(event.y_root) - window.winfo_y()

    def motion(event) -> None:
        if not state["active"]:
            return
        x = int(event.x_root) - int(state["dx"])
        y = int(event.y_root) - int(state["dy"])
        window.geometry(f"+{x}+{y}")
        state["x"], state["y"] = x, y
        state["moved"] = True

    def end(_event) -> None:
        if not state["active"]:
            return
        state["active"] = False
        if state["moved"] and on_end is not None:
            on_end(int(state["x"]), int(state["y"]))

    window.bind("<ButtonPress-1>", start, add="+")
    window.bind("<B1-Motion>", motion, add="+")
    window.bind("<ButtonRelease-1>", end, add="+")

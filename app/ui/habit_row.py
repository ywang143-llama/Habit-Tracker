"""One habit line inside the floating card."""

from __future__ import annotations

from datetime import date
from typing import Callable

import customtkinter as ctk

from ..habits import Habit
from . import theme
from .controls import CheckCircle, ellipsize, mark_no_drag, ui_scale


class HabitRow(ctk.CTkFrame):
    """A clickable row with a circular check and a streak badge."""

    def __init__(
        self,
        master,
        *,
        habit: Habit,
        today: date,
        fonts: theme.Fonts,
        max_name_width: float,
        command: Callable[[str], None],
        on_reorder_start: Callable[[str], None],
        on_reorder_move: Callable[[int], None],
        on_reorder_end: Callable[[], None],
    ) -> None:
        super().__init__(
            master,
            fg_color="transparent",
            corner_radius=10,
            height=38,
        )
        self.grid_propagate(False)
        mark_no_drag(self)

        self._habit = habit
        self._fonts = fonts
        self._command = command
        self._on_reorder_start = on_reorder_start
        self._on_reorder_move = on_reorder_move
        self._on_reorder_end = on_reorder_end
        self._done = habit.is_done(today)
        self._max_name_width = max_name_width
        self._pressed = False
        self._dragging = False
        self._drag_visual = False
        self._press_y = 0
        scale = ui_scale(self)
        self._drag_threshold = max(4, int(round(6 * scale)))

        self.grid_columnconfigure(1, weight=1, minsize=0)
        self.grid_rowconfigure(0, weight=1)

        self._check = CheckCircle(
            self,
            checked=self._done,
            command=self._on_check_clicked,
            bg_color=theme.BG,
            size=22,
        )
        self._check.grid(
            row=0,
            column=0,
            padx=(int(8 * scale), int(10 * scale)),
            pady=int(8 * scale),
            sticky="w",
        )

        display_name = ellipsize(habit.name, fonts.habit, max_name_width)
        self._name = ctk.CTkLabel(
            self,
            text=display_name,
            font=fonts.habit,
            text_color=theme.DONE_TEXT if self._done else theme.TEXT,
            anchor="w",
            height=20,
            fg_color="transparent",
        )
        self._name.grid(row=0, column=1, sticky="ew", pady=0)

        self._badge = ctk.CTkLabel(
            self,
            width=36,
            height=20,
            corner_radius=10,
            font=fonts.badge,
            anchor="center",
        )
        self._badge.grid(
            row=0,
            column=2,
            padx=(8, 8),
            pady=0,
            sticky="e",
        )
        self._set_badge(habit.streak(today))

        for widget in (self, self._name, self._badge):
            widget.bind("<ButtonPress-1>", self._on_press)
            widget.bind("<B1-Motion>", self._on_motion)
            widget.bind("<ButtonRelease-1>", self._on_release)
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass
        self._check.bind("<Enter>", self._on_enter, add="+")
        self._check.bind("<Leave>", self._on_leave, add="+")

    # ------------------------------------------------------------------ state
    def set_state(self, done: bool, streak: int) -> None:
        self._done = done
        self._check.set_state(done)
        self._name.configure(text_color=theme.DONE_TEXT if done else theme.TEXT)
        self._set_badge(streak)

    def _set_badge(self, streak: int) -> None:
        self._badge.configure(text=f"{streak}d")
        if streak <= 0:
            background, foreground = theme.STREAK_ZERO_BG, theme.STREAK_ZERO_TEXT
        elif streak < 7:
            background, foreground = theme.STREAK_BG, theme.STREAK_TEXT
        else:
            background, foreground = theme.STREAK_HOT_BG, theme.STREAK_HOT_TEXT
        self._badge.configure(fg_color=background, text_color=foreground)

    # ----------------------------------------------------------------- events
    def set_dragging(self, dragging: bool) -> None:
        self._drag_visual = dragging
        if dragging:
            self.configure(fg_color=theme.HOVER)
            self._check.set_background(theme.HOVER)
        else:
            self.configure(fg_color="transparent")
            self._check.set_background(theme.BG)

    def _on_check_clicked(self) -> None:
        self._command(self._habit.id)

    def _on_press(self, event) -> None:
        if self._drag_visual:
            return
        self._pressed = True
        self._dragging = False
        self._press_y = int(event.y_root)

    def _on_motion(self, event) -> None:
        if not self._pressed:
            return

        y_root = int(event.y_root)
        if not self._dragging and abs(y_root - self._press_y) >= self._drag_threshold:
            self._dragging = True
            self._on_reorder_start(self._habit.id)
        if self._dragging:
            self._on_reorder_move(y_root)

    def _on_release(self, _event) -> None:
        if not self._pressed:
            return

        self._pressed = False
        if self._dragging:
            self._dragging = False
            self._on_reorder_end()
        else:
            self._command(self._habit.id)

    def _on_enter(self, _event=None) -> None:
        self.configure(fg_color=theme.HOVER)
        self._check.set_background(theme.HOVER)

    def _on_leave(self, _event=None) -> None:
        if self._dragging or self._drag_visual:
            return
        # Moving between children briefly fires Leave; confirm the pointer left.
        self.after(25, self._settle_hover)

    def _settle_hover(self) -> None:
        if self._dragging or self._drag_visual:
            return
        try:
            x, y = self.winfo_pointerxy()
            widget = self.winfo_containing(x, y)
        except Exception:
            widget = None

        current = widget
        while current is not None:
            if current is self:
                return
            current = getattr(current, "master", None)

        self.configure(fg_color="transparent")
        self._check.set_background(theme.BG)

"""The small frameless window used to add and remove habits."""

from __future__ import annotations

import logging
from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from .. import win
from ..habits import HabitStore
from . import theme
from .controls import attach_drag, ellipsize, mark_no_drag, ui_scale

logger = logging.getLogger(__name__)

_MODAL_WIDTH = 344


class SettingsWindow(ctk.CTkToplevel):
    _deactivate_windows_window_header_manipulation = True

    def __init__(
        self,
        master,
        *,
        habits: HabitStore,
        fonts: theme.Fonts,
        today: date,
        on_changed: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color=theme.BG)
        self.withdraw()
        self.title("Habit Tracker Settings")
        self.overrideredirect(True)
        self.attributes("-alpha", 0.0)
        self.attributes("-topmost", True)
        try:
            self.transient(master)
        except Exception:
            pass

        self._habits = habits
        self._fonts = fonts
        self._today = today
        self._on_changed = on_changed
        self._on_close = on_close
        self._scale = ui_scale(self)
        self._armed_id: Optional[str] = None
        self._armed_button: Optional[ctk.CTkButton] = None
        self._disarm_job: Optional[str] = None
        self._shape_job: Optional[str] = None
        self._closing = False

        self._build()
        self._bind_shortcuts()
        attach_drag(self)

        self.update_idletasks()
        self._resize_card()
        self.update_idletasks()
        self._position_over_parent(master)
        win.hide_from_taskbar(self)
        self._apply_shape()

        self.deiconify()
        self.lift()
        try:
            self.grab_set()
        except Exception:
            logger.exception("Could not open the settings window as a modal")
        self.after(60, self._focus_entry)
        self.after(30, self._after_show)

    # ----------------------------------------------------------------- build
    def _build(self) -> None:
        card = ctk.CTkFrame(
            self,
            width=_MODAL_WIDTH,
            fg_color=theme.BG,
            bg_color=theme.BG,
            corner_radius=theme.CARD_RADIUS,
            border_width=1,
            border_color=theme.BORDER,
        )
        card.pack(fill="both", expand=True)
        card.pack_propagate(False)
        self._card = card

        content = ctk.CTkFrame(card, fg_color="transparent")
        self._content = content
        content.pack(
            fill="both",
            expand=True,
            padx=theme.PAD,
            pady=(15, 14),
        )

        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Manage habits",
            font=self._fonts.section,
            text_color=theme.TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        close_button = ctk.CTkButton(
            header,
            text="\u00d7",
            width=27,
            height=27,
            corner_radius=8,
            fg_color="transparent",
            hover_color=theme.HOVER,
            text_color=theme.MUTED,
            font=self._fonts.close,
            command=self.close,
        )
        close_button.grid(row=0, column=1, sticky="e")
        mark_no_drag(close_button)

        ctk.CTkLabel(
            content,
            text="Changes save automatically.",
            font=self._fonts.meta,
            text_color=theme.FAINT,
            anchor="w",
        ).pack(fill="x", pady=(2, 12))

        self._list = ctk.CTkScrollableFrame(
            content,
            height=self._list_height(),
            fg_color="transparent",
            corner_radius=0,
            scrollbar_fg_color="transparent",
            scrollbar_button_color=theme.SURFACE,
            scrollbar_button_hover_color=theme.HOVER,
        )
        self._list.pack(fill="x")
        mark_no_drag(self._list)
        self._rebuild_list()

        divider = ctk.CTkFrame(content, height=1, fg_color=theme.BORDER)
        divider.pack(fill="x", pady=(12, 12))

        ctk.CTkLabel(
            content,
            text="ADD A HABIT",
            font=self._fonts.small,
            text_color=theme.FAINT,
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        add_row = ctk.CTkFrame(content, fg_color="transparent")
        add_row.pack(fill="x")
        add_row.grid_columnconfigure(0, weight=1)

        self._entry = ctk.CTkEntry(
            add_row,
            height=32,
            corner_radius=8,
            border_width=1,
            border_color=theme.BORDER,
            fg_color=theme.SURFACE,
            text_color=theme.TEXT,
            placeholder_text="e.g. Read for 20 minutes",
            placeholder_text_color=theme.FAINT,
            font=self._fonts.body,
        )
        self._entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._entry.bind("<Return>", lambda _event: self._add_habit())
        mark_no_drag(self._entry)

        add_button = ctk.CTkButton(
            add_row,
            text="Add",
            width=62,
            height=32,
            corner_radius=8,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            text_color=theme.ON_ACCENT,
            font=self._fonts.button,
            command=self._add_habit,
        )
        add_button.grid(row=0, column=1, sticky="e")
        mark_no_drag(add_button)

        self._error = ctk.CTkLabel(
            content,
            text="",
            font=self._fonts.meta,
            text_color=theme.DANGER,
            anchor="w",
            height=16,
        )
        self._error.pack(fill="x", pady=(5, 0))

        footer = ctk.CTkFrame(content, fg_color="transparent")
        footer.pack(fill="x", pady=(4, 0))

        done_button = ctk.CTkButton(
            footer,
            text="Done",
            width=70,
            height=30,
            corner_radius=8,
            fg_color=theme.SURFACE,
            hover_color=theme.HOVER,
            text_color=theme.TEXT,
            font=self._fonts.button,
            command=self.close,
        )
        done_button.pack(side="right")
        mark_no_drag(done_button)

    def _bind_shortcuts(self) -> None:
        self.bind("<Escape>", lambda _event: self.close())
        self.bind("<Configure>", self._on_configure, add="+")

    def _on_configure(self, event) -> None:
        if event.widget is not self:
            return
        if self._shape_job is not None:
            try:
                self.after_cancel(self._shape_job)
            except Exception:
                pass
        self._shape_job = self.after(25, self._apply_shape)

    def _apply_shape(self) -> None:
        self._shape_job = None
        try:
            win.apply_rounded_corners(self, theme.CARD_RADIUS * self._scale)
        except Exception:
            logger.exception("Could not round the settings window")

    # ------------------------------------------------------------------ list
    def _list_height(self) -> int:
        if not self._habits.habits:
            return 62
        visible = min(max(len(self._habits.habits), 1), 5)
        return visible * 36

    def _rebuild_list(self) -> None:
        for child in self._list.winfo_children():
            child.destroy()
        self._armed_id = None
        self._armed_button = None
        self._cancel_disarm()

        if not self._habits.habits:
            ctk.CTkLabel(
                self._list,
                text="No habits yet. Add one below.",
                font=self._fonts.meta,
                text_color=theme.FAINT,
                height=38,
            ).pack(fill="x", pady=12)
        else:
            for habit in self._habits.habits:
                self._build_row(habit)

        self._list.configure(height=self._list_height())
        self._toggle_scrollbar()
        self._resize_card()

    def _resize_card(self) -> None:
        try:
            self.update_idletasks()
            content_height = self._content.winfo_reqheight()
            design_height = int(round(content_height / max(self._scale, 0.1))) + 31
            self._card.configure(height=design_height)
        except Exception:
            logger.debug("Could not size the settings card", exc_info=True)
        self._ensure_on_screen()

    def _ensure_on_screen(self) -> None:
        try:
            if not self.winfo_ismapped():
                return
            self.update_idletasks()
            width = max(self.winfo_width(), 1)
            height = max(self.winfo_height(), 1)
            x, y = win.clamp_to_visible(
                self.winfo_x(), self.winfo_y(), width, height, margin=20
            )
            if (x, y) != (self.winfo_x(), self.winfo_y()):
                self.geometry(f"+{x}+{y}")
        except Exception:
            logger.debug("Could not keep the settings window on screen", exc_info=True)

    def _build_row(self, habit) -> None:
        row = ctk.CTkFrame(self._list, fg_color="transparent", height=34)
        row.grid_propagate(False)
        row.pack(fill="x", pady=(0, 2))
        row.grid_columnconfigure(0, weight=1, minsize=0)

        max_width = 190 * self._scale
        ctk.CTkLabel(
            row,
            text=ellipsize(habit.name, self._fonts.body, max_width),
            font=self._fonts.body,
            text_color=theme.TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")

        streak = habit.streak(self._today)
        ctk.CTkLabel(
            row,
            text=f"{streak}d",
            width=32,
            height=18,
            corner_radius=9,
            font=self._fonts.badge,
            fg_color=theme.STREAK_ZERO_BG if streak == 0 else theme.STREAK_BG,
            text_color=theme.STREAK_ZERO_TEXT if streak == 0 else theme.STREAK_TEXT,
        ).grid(row=0, column=1, padx=(8, 6), sticky="e")

        delete_button = ctk.CTkButton(
            row,
            text="\u2715",
            width=27,
            height=24,
            corner_radius=7,
            fg_color="transparent",
            hover_color=theme.DANGER_BG,
            text_color=theme.FAINT,
            font=self._fonts.small,
            command=lambda: self._on_delete(habit, delete_button),
        )
        delete_button.grid(row=0, column=2, sticky="e")
        mark_no_drag(delete_button)

    def _toggle_scrollbar(self) -> None:
        scrollbar = getattr(self._list, "_scrollbar", None)
        if scrollbar is None:
            return
        mark_no_drag(scrollbar)
        try:
            if len(self._habits.habits) > 5:
                scrollbar.grid()
            else:
                scrollbar.grid_remove()
        except Exception:
            pass

    # ------------------------------------------------------------- mutations
    def _add_habit(self) -> None:
        try:
            self._habits.add(self._entry.get(), self._today)
        except ValueError as exc:
            self._show_error(str(exc))
            return

        self._entry.delete(0, "end")
        self._show_error("")
        self._rebuild_list()
        self._on_changed()
        self._scroll_to_bottom()
        self._entry.focus_set()

    def _scroll_to_bottom(self) -> None:
        try:
            canvas = getattr(self._list, "_parent_canvas", None)
            if canvas is not None:
                self.update_idletasks()
                canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _on_delete(self, habit, button) -> None:
        if self._armed_id != habit.id:
            self._arm_delete(habit, button)
            return

        self._cancel_disarm()
        self._armed_id = None
        self._armed_button = None
        if self._habits.remove(habit.id):
            self._rebuild_list()
            self._on_changed()

    def _arm_delete(self, habit, button) -> None:
        self._disarm_armed_button()
        self._cancel_disarm()
        self._armed_id = habit.id
        self._armed_button = button
        try:
            button.configure(
                text="Remove?",
                width=68,
                fg_color=theme.DANGER_BG,
                text_color=theme.DANGER,
                hover_color=theme.DANGER_HOVER,
            )
        except Exception:
            return
        self._disarm_job = self.after(3500, self._disarm_armed_button)

    def _disarm_armed_button(self) -> None:
        self._cancel_disarm()
        button = self._armed_button
        self._armed_id = None
        self._armed_button = None
        if button is None:
            return
        try:
            if button.winfo_exists():
                button.configure(
                    text="\u2715",
                    width=27,
                    fg_color="transparent",
                    text_color=theme.FAINT,
                    hover_color=theme.DANGER_BG,
                )
        except Exception:
            pass

    def _cancel_disarm(self) -> None:
        if self._disarm_job is not None:
            try:
                self.after_cancel(self._disarm_job)
            except Exception:
                pass
            self._disarm_job = None

    def _show_error(self, message: str) -> None:
        self._error.configure(text=message)

    # ---------------------------------------------------------------- window
    def _position_over_parent(self, parent) -> None:
        width = max(self.winfo_reqwidth(), 1)
        height = max(self.winfo_reqheight(), 1)
        try:
            x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
        except Exception:
            x, y = 200, 200
        x, y = win.clamp_to_visible(x, y, width, height, margin=20)
        self.geometry(f"+{x}+{y}")

    def _focus_entry(self) -> None:
        if not self.winfo_exists():
            return
        try:
            self.focus_force()
            self._entry.focus_set()
        except Exception:
            pass

    def _after_show(self) -> None:
        if not self.winfo_exists():
            return
        try:
            win.hide_from_taskbar(self)
            self._apply_shape()
        finally:
            try:
                self.attributes("-alpha", 1.0)
            except Exception:
                pass

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._cancel_disarm()
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        try:
            self._on_close()
        except Exception:
            logger.exception("Settings close callback failed")

    def destroy(self) -> None:
        if self._shape_job is not None:
            try:
                self.after_cancel(self._shape_job)
            except Exception:
                pass
            self._shape_job = None
        super().destroy()

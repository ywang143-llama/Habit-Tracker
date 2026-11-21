"""The frameless floating habit card."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date
from typing import Callable, Optional

import customtkinter as ctk

from .. import win
from ..config import ConfigStore
from ..habits import HabitStore
from ..paths import asset_path
from . import theme
from .controls import attach_drag, mark_no_drag, ui_scale
from .habit_row import HabitRow
from .settings import SettingsWindow

logger = logging.getLogger(__name__)

_MAX_VISIBLE_ROWS = 7
_ROW_HEIGHT = 52  # design pixels, including spacing


class FloatingWidget(ctk.CTk):
    # The window has no titlebar, so CustomTkinter's DWM titlebar handling is
    # unnecessary (and it would hide/show the window during startup).
    _deactivate_windows_window_header_manipulation = True

    def __init__(
        self,
        *,
        config: ConfigStore,
        habits: HabitStore,
        notify: Optional[Callable[[str, str], None]] = None,
        on_hide_request: Optional[Callable[[], None]] = None,
        on_close_request: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(fg_color=theme.BG)
        self.withdraw()

        self.config = config
        self.habits = habits
        self._notify = notify
        self._on_hide_request = on_hide_request
        self._on_close_request = on_close_request
        self._today = date.today()
        self._topmost = config.config.always_on_top
        self._rows: dict[str, HabitRow] = {}
        self._settings: Optional[SettingsWindow] = None
        self._shape_job: Optional[str] = None
        self._day_job: Optional[str] = None
        self._scale = 1.0
        self._reorder_id: Optional[str] = None
        self._reorder_from: Optional[int] = None
        self._reorder_to: Optional[int] = None
        self._reorder_indicator: Optional[tk.Frame] = None

        self.title("Habit Tracker")
        self.overrideredirect(True)
        self.attributes("-alpha", 0.0)
        self.attributes("-topmost", self._topmost)

        icon_path = asset_path("icon.ico")
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                logger.debug("Could not set the window icon", exc_info=True)

        self.fonts = theme.Fonts()
        self._scale = ui_scale(self)

        self._build()
        self._restore_position()
        attach_drag(self, on_end=self.persist_position)
        self.protocol("WM_DELETE_WINDOW", self._request_hide)

        self.update_idletasks()
        win.hide_from_taskbar(self)
        self.deiconify()
        self.after(20, self._after_show)
        self._day_job = self.after(1500, self._check_day)

    # ------------------------------------------------------------------ setup
    def _build(self) -> None:
        self._card = ctk.CTkFrame(
            self,
            width=theme.WINDOW_WIDTH,
            fg_color=theme.BG,
            bg_color=theme.BG,
            corner_radius=theme.CARD_RADIUS,
            border_width=1,
            border_color=theme.BORDER,
        )
        self._card.pack(fill="both", expand=True)
        self._card.pack_propagate(False)

        content = ctk.CTkFrame(self._card, fg_color="transparent")
        self._content = content
        content.pack(
            fill="both",
            expand=True,
            padx=theme.PAD,
            pady=(15, 15),
        )

        # Header -------------------------------------------------------------
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Today",
            font=self.fonts.title,
            text_color=theme.TEXT,
            anchor="w",
            height=22,
        ).grid(row=0, column=0, sticky="w")

        self._date_label = ctk.CTkLabel(
            header,
            text="",
            font=self.fonts.date,
            text_color=theme.MUTED,
            anchor="w",
            height=15,
        )
        self._date_label.grid(row=1, column=0, sticky="w", pady=(2, 0))

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=1, rowspan=2, sticky="e")

        self._settings_button = ctk.CTkButton(
            controls,
            text="\u2699",
            width=28,
            height=28,
            corner_radius=9,
            fg_color="transparent",
            hover_color=theme.HOVER,
            text_color=theme.MUTED,
            font=self.fonts.icon,
            command=self.open_settings,
        )
        self._minimize_button = ctk.CTkButton(
            controls,
            text="\u2013",
            width=28,
            height=28,
            corner_radius=9,
            fg_color="transparent",
            hover_color=theme.HOVER,
            text_color=theme.MUTED,
            font=self.fonts.close,
            command=self._request_hide,
        )
        self._close_button = ctk.CTkButton(
            controls,
            text="\u00d7",
            width=28,
            height=28,
            corner_radius=9,
            fg_color="transparent",
            hover_color=theme.DANGER_BG,
            text_color=theme.MUTED,
            font=self.fonts.close,
            command=self._request_close,
        )

        self._settings_button.pack(side="left", padx=(0, 4))
        self._minimize_button.pack(side="left", padx=(0, 4))
        self._close_button.pack(side="left")
        for button in (
            self._settings_button,
            self._minimize_button,
            self._close_button,
        ):
            mark_no_drag(button)

        # Body ---------------------------------------------------------------
        self._body = ctk.CTkFrame(content, fg_color="transparent")
        self._body.pack(fill="x", pady=(12, 0))

        self._list = ctk.CTkScrollableFrame(
            self._body,
            height=_ROW_HEIGHT,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_fg_color="transparent",
            scrollbar_button_color=theme.SURFACE,
            scrollbar_button_hover_color=theme.HOVER,
        )

        self._empty = ctk.CTkFrame(
            self._body,
            fg_color=theme.SURFACE,
            corner_radius=12,
        )
        empty_inner = ctk.CTkFrame(self._empty, fg_color="transparent")
        empty_inner.pack(
            fill="both",
            expand=True,
            padx=14,
            pady=16,
        )
        ctk.CTkLabel(
            empty_inner,
            text="No habits yet",
            font=self.fonts.empty_title,
            text_color=theme.TEXT,
        ).pack()
        ctk.CTkLabel(
            empty_inner,
            text="Add one to start building a streak.",
            font=self.fonts.meta,
            text_color=theme.MUTED,
        ).pack(pady=(3, 12))
        empty_add = ctk.CTkButton(
            empty_inner,
            text="Add a habit",
            width=112,
            height=30,
            corner_radius=8,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            text_color=theme.ON_ACCENT,
            font=self.fonts.button,
            command=self.open_settings,
        )
        empty_add.pack()
        mark_no_drag(empty_add)

        # Footer -------------------------------------------------------------
        self._footer = ctk.CTkFrame(content, fg_color="transparent")

        summary_row = ctk.CTkFrame(self._footer, fg_color="transparent")
        summary_row.pack(fill="x")
        summary_row.grid_columnconfigure(0, weight=1)

        self._summary_label = ctk.CTkLabel(
            summary_row,
            text="",
            font=self.fonts.meta,
            text_color=theme.MUTED,
            anchor="w",
        )
        self._summary_label.grid(row=0, column=0, sticky="w")

        self._percent_label = ctk.CTkLabel(
            summary_row,
            text="",
            font=self.fonts.meta,
            text_color=theme.FAINT,
            anchor="e",
        )
        self._percent_label.grid(row=0, column=1, sticky="e")

        self._progress = ctk.CTkProgressBar(
            self._footer,
            height=4,
            corner_radius=2,
            border_width=0,
            fg_color=theme.TRACK,
            progress_color=theme.ACCENT,
        )
        self._progress.pack(fill="x", pady=(7, 0))
        self._progress.set(0)

        self.bind("<Configure>", self._on_configure, add="+")
        self._rebuild()

    # ----------------------------------------------------------------- filling
    def _rebuild(self) -> None:
        self._clear_reorder()
        for row in self._rows.values():
            row.destroy()
        self._rows.clear()

        total = len(self.habits.habits)
        if total == 0:
            self._list.pack_forget()
            self._empty.pack(fill="x")
            self._footer.pack_forget()
        else:
            self._empty.pack_forget()
            self._list.pack(fill="x")
            self._footer.pack(fill="x", pady=(11, 0))

            max_name_width = 142 * self._scale
            for habit in self.habits.habits:
                row = HabitRow(
                    self._list,
                    habit=habit,
                    today=self._today,
                    fonts=self.fonts,
                    max_name_width=max_name_width,
                    command=self._toggle_habit,
                    on_reorder_start=self._begin_reorder,
                    on_reorder_move=self._move_reorder,
                    on_reorder_end=self._end_reorder,
                )
                row.pack(fill="x", pady=(0, 2))
                self._rows[habit.id] = row

            visible_rows = min(total, _MAX_VISIBLE_ROWS)
            self._list.configure(height=visible_rows * _ROW_HEIGHT)
            self._toggle_scrollbar(total > _MAX_VISIBLE_ROWS)

        self._update_date()
        self._update_summary()
        self.update_idletasks()
        self._resize_card()
        self._ensure_on_screen()
        self._schedule_shape()

    def _resize_card(self) -> None:
        """Give the card its fixed width and fit its height to the content."""
        try:
            content_height = self._content.winfo_reqheight()
            design_height = int(round(content_height / max(self._scale, 0.1))) + 32
            self._card.configure(height=design_height)
        except Exception:
            logger.debug("Could not size the habit card", exc_info=True)

    def _toggle_scrollbar(self, show: bool) -> None:
        scrollbar = getattr(self._list, "_scrollbar", None)
        if scrollbar is None:
            return
        mark_no_drag(scrollbar)
        try:
            if show:
                scrollbar.grid()
            else:
                scrollbar.grid_remove()
        except Exception:
            pass

    def _update_date(self) -> None:
        try:
            self._date_label.configure(text=f"{self._today:%a, %b} {self._today.day}")
        except Exception:
            pass

    def _update_summary(self) -> None:
        total = len(self.habits.habits)
        if total == 0:
            return
        done = self.habits.done_count(self._today)
        self._progress.set(done / total)
        if done == total:
            self._summary_label.configure(
                text="All done today", text_color=theme.ACCENT
            )
        else:
            self._summary_label.configure(
                text=f"{done} of {total} complete", text_color=theme.MUTED
            )
        self._percent_label.configure(text=f"{round(done / total * 100)}%")

    # ---------------------------------------------------------------- behavior
    def _toggle_habit(self, habit_id: str) -> None:
        try:
            done = self.habits.toggle(habit_id, self._today)
        except KeyError:
            return
        self._save_habits()

        habit = self.habits.get(habit_id)
        row = self._rows.get(habit_id)
        if habit is not None and row is not None:
            row.set_state(done, habit.streak(self._today))
        self._update_summary()

    # --------------------------------------------------------------- reordering
    def _begin_reorder(self, habit_id: str) -> None:
        if self._reorder_id is not None:
            return

        index = next(
            (i for i, habit in enumerate(self.habits.habits) if habit.id == habit_id),
            None,
        )
        if index is None:
            return

        self._reorder_id = habit_id
        self._reorder_from = index
        self._reorder_to = index
        row = self._rows.get(habit_id)
        if row is not None:
            row.set_dragging(True)
        self._ensure_reorder_indicator()

    def _move_reorder(self, y_root: int) -> None:
        if self._reorder_id is None or self._reorder_from is None:
            return

        slot = self._reorder_slot(int(y_root))
        target = slot - 1 if slot > self._reorder_from else slot
        target = max(0, min(target, len(self.habits.habits) - 1))
        self._reorder_to = target
        self._place_reorder_indicator(slot)

    def _end_reorder(self) -> None:
        habit_id = self._reorder_id
        original = self._reorder_from
        target = self._reorder_to
        self._clear_reorder()

        if habit_id is None or original is None or target is None:
            return
        if target == original:
            return
        if self.habits.move(habit_id, target):
            self._save_habits()
            self._repack_rows()

    def _clear_reorder(self) -> None:
        if self._reorder_id is not None:
            row = self._rows.get(self._reorder_id)
            if row is not None:
                try:
                    row.set_dragging(False)
                except Exception:
                    pass
        if self._reorder_indicator is not None:
            try:
                self._reorder_indicator.place_forget()
            except Exception:
                pass
        self._reorder_id = None
        self._reorder_from = None
        self._reorder_to = None

    def _ordered_rows(self) -> list[HabitRow]:
        return [
            self._rows[habit.id]
            for habit in self.habits.habits
            if habit.id in self._rows
        ]

    def _reorder_slot(self, y_root: int) -> int:
        rows = self._ordered_rows()
        for index, row in enumerate(rows):
            center = row.winfo_rooty() + row.winfo_height() // 2
            if y_root < center:
                return index
        return len(rows)

    def _ensure_reorder_indicator(self) -> None:
        if (
            self._reorder_indicator is not None
            and self._reorder_indicator.winfo_exists()
        ):
            return
        self._reorder_indicator = tk.Frame(self._list, bg=theme.ACCENT)

    def _place_reorder_indicator(self, slot: int) -> None:
        rows = self._ordered_rows()
        indicator = self._reorder_indicator
        if not rows or indicator is None or not indicator.winfo_exists():
            return

        height = max(2, int(round(2 * self._scale)))
        if slot >= len(rows):
            y = (
                rows[-1].winfo_y()
                + rows[-1].winfo_height()
                + int(round(1 * self._scale))
            )
        else:
            y = rows[slot].winfo_y() - int(round(2 * self._scale))

        indicator.place(x=0, y=max(0, y), relwidth=1, height=height)
        indicator.lift()

    def _repack_rows(self) -> None:
        """Apply the new order without rebuilding (keeps the scroll position)."""
        canvas = getattr(self._list, "_parent_canvas", None)
        offset: Optional[float] = None
        if canvas is not None:
            try:
                offset = float(canvas.yview()[0])
            except Exception:
                offset = None

        for habit in self.habits.habits:
            row = self._rows.get(habit.id)
            if row is not None:
                row.pack_forget()
        for habit in self.habits.habits:
            row = self._rows.get(habit.id)
            if row is not None:
                row.pack(fill="x", pady=(0, 2))

        if canvas is not None and offset is not None:
            self.after_idle(lambda: self._restore_scroll(offset))
        self._update_summary()

    def _restore_scroll(self, offset: float) -> None:
        canvas = getattr(self._list, "_parent_canvas", None)
        if canvas is None:
            return
        try:
            canvas.yview_moveto(offset)
        except Exception:
            pass

    def _save_habits(self) -> None:
        try:
            self.habits.save()
        except OSError as exc:
            logger.exception("Could not save habits")
            self._notify_safely("Couldn't save your habits", str(exc))

    def _habits_changed(self) -> None:
        self._save_habits()
        self._rebuild()

    def _notify_safely(self, title: str, message: str) -> None:
        if self._notify is None:
            return
        try:
            self._notify(title, message)
        except Exception:
            logger.exception("Tray notification failed")

    # ----------------------------------------------------------------- settings
    def open_settings(self) -> None:
        if self._settings is not None:
            try:
                if self._settings.winfo_exists():
                    self._settings.lift()
                    self._settings.focus_force()
                    return
            except Exception:
                pass
            self._settings = None

        self._settings = SettingsWindow(
            self,
            habits=self.habits,
            fonts=self.fonts,
            today=self._today,
            on_changed=self._habits_changed,
            on_close=self._settings_closed,
        )

    def _settings_closed(self) -> None:
        self._settings = None

    def close_settings(self) -> None:
        settings = self._settings
        self._settings = None
        if settings is None:
            return
        try:
            if settings.winfo_exists():
                settings.close()
        except Exception:
            logger.exception("Could not close the settings window")

    # -------------------------------------------------------------------- window
    def _restore_position(self) -> None:
        self._resize_card()
        self.update_idletasks()
        width = max(self.winfo_reqwidth(), 1)
        height = max(self.winfo_reqheight(), 1)

        if self.config.config.x is None or self.config.config.y is None:
            x, y = win.default_position(width, height)
        else:
            x, y = win.clamp_to_visible(
                self.config.config.x, self.config.config.y, width, height
            )
        self.geometry(f"+{x}+{y}")

    def persist_position(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        try:
            if x is None or y is None:
                x, y = self.winfo_x(), self.winfo_y()
            self.config.set_position(int(x), int(y))
        except Exception:
            logger.exception("Could not persist the window position")

    def _ensure_on_screen(self) -> None:
        try:
            if not self.winfo_ismapped():
                return
            self.update_idletasks()
            width = max(self.winfo_width(), 1)
            height = max(self.winfo_height(), 1)
            x, y = win.clamp_to_visible(
                self.winfo_x(), self.winfo_y(), width, height
            )
            if (x, y) != (self.winfo_x(), self.winfo_y()):
                self.geometry(f"+{x}+{y}")
                self.persist_position()
        except Exception:
            logger.debug("Could not keep the widget on screen", exc_info=True)

    def _on_configure(self, event) -> None:
        if event.widget is not self:
            return
        self._schedule_shape()

    def _schedule_shape(self) -> None:
        if self._shape_job is not None:
            try:
                self.after_cancel(self._shape_job)
            except Exception:
                pass
        self._shape_job = self.after(25, self._apply_shape)

    def _apply_shape(self) -> None:
        self._shape_job = None
        try:
            current_scale = ui_scale(self)
            if abs(current_scale - self._scale) > 0.01:
                # The widget moved to a monitor with a different DPI. Rebuild
                # so truncation and card sizing use the new scale.
                self._scale = current_scale
                self._rebuild()
                return
            win.apply_rounded_corners(self, theme.CARD_RADIUS * self._scale)
        except Exception:
            logger.debug("Could not round the window", exc_info=True)

    def _after_show(self) -> None:
        if not self.winfo_exists():
            return
        try:
            win.hide_from_taskbar(self)
            self.attributes("-topmost", self._topmost)
            self._apply_shape()
            self.lift()
            self._ensure_on_screen()
        finally:
            self.attributes("-alpha", theme.WINDOW_OPACITY)
        self.after(250, self.persist_position)
        self.after(600, lambda: win.hide_from_taskbar(self))

    def _request_hide(self) -> None:
        if self._on_hide_request is not None:
            self._on_hide_request()
        else:
            self.hide()

    def _request_close(self) -> None:
        if self._on_close_request is not None:
            self._on_close_request()
        else:
            self.hide()

    def show(self) -> None:
        self._check_day()
        self.deiconify()
        self.attributes("-alpha", theme.WINDOW_OPACITY)
        self.attributes("-topmost", self._topmost)
        self.lift()
        self._apply_shape()
        self._ensure_on_screen()
        self.after(80, lambda: win.hide_from_taskbar(self))

    def hide(self) -> None:
        self.close_settings()
        self.persist_position()
        self.withdraw()

    def apply_always_on_top(self, value: bool) -> None:
        self._topmost = bool(value)
        self.attributes("-topmost", self._topmost)
        if self._topmost:
            self.lift()

    @property
    def always_on_top(self) -> bool:
        return self._topmost

    # -------------------------------------------------------------------- clock
    def _check_day(self) -> None:
        if not self.winfo_exists():
            return
        today = date.today()
        if today != self._today:
            self._today = today
            self._rebuild()
        self._day_job = self.after(20000, self._check_day)

    def destroy(self) -> None:
        for job in (self._shape_job, self._day_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        self._shape_job = None
        self._day_job = None
        self.close_settings()
        super().destroy()

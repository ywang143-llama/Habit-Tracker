"""Glue between the Tk widget, the data stores, and the tray icon."""

from __future__ import annotations

import logging
import queue
import traceback
from pathlib import Path
from typing import Callable, Optional

from . import startup
from .config import ConfigStore
from .habits import HabitStore
from .tray import TrayIcon
from .ui.widget import FloatingWidget

logger = logging.getLogger(__name__)


class TrackerApp:
    def __init__(self, data_directory: Path, main_script: Path) -> None:
        self._data_directory = data_directory
        self._main_script = main_script
        self._commands: queue.Queue[Callable[[], None]] = queue.Queue()
        self._quitting = False
        self._shutdown_done = False
        self._visible = True
        self._tray: Optional[TrayIcon] = None

        self.config = ConfigStore(data_directory / "config.json")
        self.habits = HabitStore(data_directory / "habits.json")

        self.widget = FloatingWidget(
            config=self.config,
            habits=self.habits,
            notify=self._notify,
            on_hide_request=self.hide,
            on_close_request=self.quit,
        )
        self.widget.report_callback_exception = self._report_callback_exception

        self._tray = TrayIcon(
            dispatch=self._dispatch,
            on_show_hide=self.toggle_visibility,
            on_settings=self.open_settings,
            on_toggle_topmost=self.toggle_topmost,
            on_toggle_startup=self.toggle_startup,
            on_quit=self.quit,
            is_visible=lambda: self._visible,
            is_topmost=lambda: self.widget.always_on_top,
            is_startup_enabled=startup.is_enabled,
        )

    # ------------------------------------------------------------------- loop
    def run(self) -> None:
        self._tray.start()
        try:
            self.widget.after(60, self._pump_commands)
            self.widget.mainloop()
        except Exception:
            logger.exception("The UI loop stopped unexpectedly")
        finally:
            self._shutdown()

    def _dispatch(self, action: Callable[[], None]) -> None:
        """Called from the tray thread; the Tk loop executes it safely."""
        self._commands.put(action)

    def _pump_commands(self) -> None:
        while True:
            try:
                action = self._commands.get_nowait()
            except queue.Empty:
                break
            try:
                action()
            except Exception:
                logger.exception("A tray action failed")

        if not self._quitting:
            try:
                self.widget.after(60, self._pump_commands)
            except Exception:
                pass

    # -------------------------------------------------------------- visibility
    def toggle_visibility(self) -> None:
        if self._visible:
            self.hide()
        else:
            self.show()

    def show(self) -> None:
        self.widget.show()
        self._visible = True
        self._refresh_tray()

    def hide(self) -> None:
        if not self._visible:
            return
        self.widget.hide()
        self._visible = False
        self._refresh_tray()

    # -------------------------------------------------------------------- menu
    def open_settings(self) -> None:
        self.show()
        self.widget.open_settings()

    def toggle_topmost(self) -> None:
        value = not self.widget.always_on_top
        self.widget.apply_always_on_top(value)
        self.config.set_always_on_top(value)
        self._refresh_tray()

    def toggle_startup(self) -> None:
        try:
            enabled = not startup.is_enabled()
            startup.set_enabled(enabled, self._main_script)
        except startup.StartupError as exc:
            logger.error("Could not change the startup setting: %s", exc)
            self._notify("Start with Windows", str(exc))
            self._refresh_tray()
            return

        if enabled:
            self._notify(
                "Habit Tracker will start with Windows.",
                "Start with Windows",
            )
        else:
            self._notify(
                "Habit Tracker will no longer start with Windows.",
                "Start with Windows",
            )
        self._refresh_tray()

    def quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        try:
            self.widget.quit()
        except Exception:
            logger.exception("Could not stop the UI loop")

    # ---------------------------------------------------------------- shutdown
    def _shutdown(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True

        try:
            self.widget.close_settings()
        except Exception:
            logger.exception("Could not close settings during shutdown")

        try:
            if self.widget.winfo_exists():
                self.widget.persist_position()
        except Exception:
            logger.debug("Could not save the final window position", exc_info=True)

        try:
            self.config.save()
        except Exception:
            logger.exception("Could not save the final configuration")

        if self._tray is not None:
            self._tray.stop()

        try:
            if self.widget.winfo_exists():
                self.widget.destroy()
        except Exception:
            logger.debug("Could not destroy the widget during shutdown", exc_info=True)

    # ------------------------------------------------------------------ helpers
    def _refresh_tray(self) -> None:
        if self._tray is not None:
            self._tray.refresh()

    def _notify(self, message: str, title: str = "Habit Tracker") -> None:
        logger.info("%s: %s", title, message)
        if self._tray is not None:
            self._tray.notify(message, title)

    def _report_callback_exception(self, exc, value, tb) -> None:
        logger.error(
            "Unhandled UI error:\n%s",
            "".join(traceback.format_exception(exc, value, tb)),
        )

"""System tray icon and menu."""

from __future__ import annotations

import logging
from typing import Callable

import pystray

from .icon import build_icon_image

logger = logging.getLogger(__name__)


class TrayIcon:
    def __init__(
        self,
        *,
        dispatch: Callable[[Callable[[], None]], None],
        on_show_hide: Callable[[], None],
        on_settings: Callable[[], None],
        on_toggle_topmost: Callable[[], None],
        on_toggle_startup: Callable[[], None],
        on_quit: Callable[[], None],
        is_visible: Callable[[], bool],
        is_topmost: Callable[[], bool],
        is_startup_enabled: Callable[[], bool],
    ) -> None:
        self._dispatch = dispatch
        self._started = False

        menu = pystray.Menu(
            pystray.MenuItem(
                lambda _item: "Hide widget" if is_visible() else "Show widget",
                lambda: dispatch(on_show_hide),
                default=True,
            ),
            pystray.MenuItem(
                "Manage habits\u2026",
                lambda: dispatch(on_settings),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Always on top",
                lambda: dispatch(on_toggle_topmost),
                checked=lambda _item: is_topmost(),
            ),
            pystray.MenuItem(
                "Start with Windows",
                lambda: dispatch(on_toggle_startup),
                checked=lambda _item: is_startup_enabled(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Quit",
                lambda: dispatch(on_quit),
            ),
        )

        self._icon = pystray.Icon(
            "habit_tracker",
            icon=build_icon_image(64),
            title="Habit Tracker",
            menu=menu,
        )

    def start(self) -> None:
        try:
            self._icon.run_detached()
            self._started = True
        except Exception:
            logger.exception("Could not start the tray icon")

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        try:
            self._icon.stop()
        except Exception:
            logger.exception("Could not stop the tray icon")

    def refresh(self) -> None:
        if not self._started:
            return
        try:
            self._icon.update_menu()
        except Exception:
            logger.exception("Could not refresh the tray menu")

    def notify(self, message: str, title: str = "Habit Tracker") -> None:
        try:
            self._icon.notify(message, title)
        except Exception:
            logger.exception("Could not show a tray notification")

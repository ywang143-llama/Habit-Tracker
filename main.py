"""Entry point for the floating habit tracker."""

from __future__ import annotations

import ctypes
import logging
import logging.handlers
import sys
import threading
from pathlib import Path

LOG_FILENAME = "habit_tracker.log"
MUTEX_NAME = "Local\\HabitTrackerWidget"


def _message_box(message: str, title: str = "Habit Tracker") -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
            return
        except Exception:
            pass
    print(f"{title}: {message}", file=sys.stderr)


def _setup_logging(directory: Path) -> None:
    formatter = logging.Formatter(
        "%(asctime)s  %(levelname)-8s %(name)s: %(message)s"
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    try:
        handler = logging.handlers.RotatingFileHandler(
            directory / LOG_FILENAME,
            maxBytes=512 * 1024,
            backupCount=1,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)
    except OSError:
        pass

    if sys.stderr is not None:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        root.addHandler(stream)

    if not root.handlers:
        root.addHandler(logging.NullHandler())


def _install_exception_hooks() -> None:
    def handle_exception(exc_type, exc_value, exc_tb):
        logging.getLogger("habit_tracker").error(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_tb),
        )

    sys.excepthook = handle_exception

    def handle_thread_exception(args):
        logging.getLogger("habit_tracker.threads").error(
            "Unhandled thread exception",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = handle_thread_exception


def main() -> int:
    if sys.platform != "win32":
        _message_box("Habit Tracker is designed for Windows 10 and 11.")
        return 1

    try:
        import customtkinter  # noqa: F401
        import pystray  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        _message_box(
            "Habit Tracker needs a few Python packages that are not installed.\n\n"
            "Open a terminal in this folder and run:\n"
            "    python -m pip install -r requirements.txt\n\n"
            f"Details: {exc}"
        )
        return 1

    from app.paths import data_dir

    try:
        data_directory = data_dir()
    except OSError as exc:
        _message_box(f"Habit Tracker could not create its data folder.\n\n{exc}")
        return 1

    _setup_logging(data_directory)
    _install_exception_hooks()
    logger = logging.getLogger("habit_tracker")

    try:
        from app import win
        from app.controller import TrackerApp

        if not win.acquire_single_instance(MUTEX_NAME):
            logger.info("Habit Tracker is already running; exiting.")
            return 0

        win.enable_dpi_awareness()

        import customtkinter as ctk

        ctk.set_appearance_mode("dark")

        app = TrackerApp(data_directory, Path(__file__).resolve())
        app.run()
        return 0
    except Exception:
        logger.exception("Habit Tracker could not start")
        _message_box(
            "Habit Tracker could not start.\n\n"
            "See habit_tracker.log in the application folder for details."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

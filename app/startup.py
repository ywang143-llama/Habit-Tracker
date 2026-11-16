"""Add or remove the app from the per-user Windows Startup folder."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .paths import asset_path

logger = logging.getLogger(__name__)

SHORTCUT_NAME = "Habit Tracker.lnk"
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class StartupError(RuntimeError):
    """Raised when the startup shortcut cannot be changed."""


def startup_folder() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise StartupError("The APPDATA folder is not available.")
    return (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


def shortcut_path() -> Path:
    return startup_folder() / SHORTCUT_NAME


def is_enabled() -> bool:
    try:
        return shortcut_path().exists()
    except (OSError, StartupError):
        return False


def launch_command(main_script: Path) -> tuple[Path, str, Path]:
    """Return (executable, arguments, working directory) for the shortcut."""
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable)
        return executable, "", executable.parent

    executable = Path(sys.executable)
    if executable.name.casefold() == "python.exe":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            executable = pythonw

    script = Path(main_script).resolve()
    return executable, f'"{script}"', script.parent


def set_enabled(enabled: bool, main_script: Path) -> None:
    """Create or remove the Startup shortcut."""
    link = shortcut_path()

    if not enabled:
        try:
            link.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise StartupError(f"Could not remove {link.name}: {exc}") from exc
        return

    try:
        link.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StartupError(f"Could not open the Startup folder: {exc}") from exc

    target, arguments, workdir = launch_command(main_script)
    if getattr(sys, "frozen", False):
        # The executable carries the app icon; the one-file extraction folder
        # is temporary, so never point a shortcut at an asset inside it.
        icon_location = str(target)
    else:
        icon = asset_path("icon.ico")
        icon_location = str(icon if icon.exists() else target)

    _create_shortcut(link, target, arguments, workdir, f"{icon_location},0")


def _create_shortcut(
    link: Path,
    target: Path,
    arguments: str,
    workdir: Path,
    icon_location: str,
) -> None:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        raise StartupError("Windows PowerShell could not be found.")

    script = (
        "$ErrorActionPreference = 'Stop'; "
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$shortcut = $ws.CreateShortcut({_ps_quote(str(link))}); "
        f"$shortcut.TargetPath = {_ps_quote(str(target))}; "
        f"$shortcut.Arguments = {_ps_quote(arguments)}; "
        f"$shortcut.WorkingDirectory = {_ps_quote(str(workdir))}; "
        f"$shortcut.IconLocation = {_ps_quote(icon_location)}; "
        "$shortcut.Description = 'Floating daily habit tracker'; "
        "$shortcut.Save();"
    )

    try:
        result = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            creationflags=_CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StartupError(f"Could not create the startup shortcut: {exc}") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        logger.error("PowerShell shortcut creation failed: %s", detail)
        raise StartupError(
            "Windows could not create the startup shortcut."
            + (f" {detail.splitlines()[-1]}" if detail else "")
        )

    if not link.exists():
        raise StartupError("The startup shortcut was not created.")


def _ps_quote(value: str) -> str:
    """Quote a value for a single-quoted PowerShell string literal."""
    return "'" + value.replace("'", "''") + "'"

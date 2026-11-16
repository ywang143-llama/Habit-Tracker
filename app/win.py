"""Thin Windows helpers: rounded corners, taskbar hiding, positioning."""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from typing import Optional

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

GA_ROOT = 2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
SPI_GETWORKAREA = 0x0030
ERROR_ALREADY_EXISTS = 183


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


if IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    _user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    _user32.GetAncestor.restype = wintypes.HWND

    _user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.GetWindowLongW.restype = ctypes.c_long
    _user32.SetWindowLongW.argtypes = [
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_long,
    ]
    _user32.SetWindowLongW.restype = ctypes.c_long

    _user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    _user32.SetWindowPos.restype = wintypes.BOOL

    _gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
    _gdi32.CreateRoundRectRgn.restype = wintypes.HANDLE
    _user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.BOOL]
    _user32.SetWindowRgn.restype = ctypes.c_int
    _gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
    _gdi32.DeleteObject.restype = wintypes.BOOL

    _user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    _user32.GetSystemMetrics.restype = ctypes.c_int

    _user32.SystemParametersInfoW.argtypes = [
        wintypes.UINT,
        wintypes.UINT,
        ctypes.POINTER(_RECT),
        wintypes.UINT,
    ]
    _user32.SystemParametersInfoW.restype = wintypes.BOOL

    _kernel32.CreateMutexW.argtypes = [
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    _kernel32.CreateMutexW.restype = wintypes.HANDLE
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL

_single_instance_handle: Optional[int] = None


def enable_dpi_awareness() -> None:
    """Make Tk render crisply on scaled displays.

    This must run before Tk creates its first window; CustomTkinter otherwise
    enables awareness too late and the fonts and layout scale inconsistently.
    """
    if not IS_WINDOWS:
        return

    try:
        _user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        _user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
        if _user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass

    try:
        _user32.SetProcessDPIAware()
    except Exception:
        pass


def top_level_hwnd(window) -> int:
    """Return the native top-level HWND for a Tk/CTk window."""
    if not IS_WINDOWS:
        return 0
    window.update_idletasks()
    hwnd = int(window.winfo_id())
    root = _user32.GetAncestor(hwnd, GA_ROOT)
    return int(root or hwnd)


def hide_from_taskbar(window) -> None:
    """Keep the window out of the taskbar and Alt+Tab."""
    if not IS_WINDOWS:
        return
    try:
        hwnd = top_level_hwnd(window)
        if not hwnd:
            return
        style = int(_user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
        new_style = (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        if new_style != style:
            _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        _user32.SetWindowPos(
            hwnd,
            None,
            0,
            0,
            0,
            0,
            SWP_NOMOVE
            | SWP_NOSIZE
            | SWP_NOZORDER
            | SWP_NOACTIVATE
            | SWP_FRAMECHANGED,
        )
    except Exception:
        logger.exception("Could not hide window from the taskbar")


def apply_rounded_corners(window, radius: float) -> None:
    """Clip the native window to a rounded rectangle."""
    if not IS_WINDOWS:
        return
    try:
        hwnd = top_level_hwnd(window)
        width = max(int(window.winfo_width()), 1)
        height = max(int(window.winfo_height()), 1)
        if not hwnd or width <= 1 or height <= 1:
            return

        diameter = max(int(round(radius * 2)), 0)
        # A diameter of zero means square corners.
        region = _gdi32.CreateRoundRectRgn(
            0, 0, width + 1, height + 1, diameter, diameter
        )
        if not region:
            return
        if not _user32.SetWindowRgn(hwnd, region, True):
            _gdi32.DeleteObject(region)
    except Exception:
        logger.exception("Could not apply rounded window corners")


def virtual_screen_rect() -> tuple[int, int, int, int]:
    """Return (left, top, width, height) covering every monitor."""
    if not IS_WINDOWS:
        return (0, 0, 1920, 1080)
    left = _user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = _user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width = _user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    height = _user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    if width <= 0 or height <= 0:
        return (0, 0, 1920, 1080)
    return (left, top, width, height)


def primary_work_area() -> tuple[int, int, int, int]:
    """Return (left, top, right, bottom) of the primary monitor's work area."""
    if IS_WINDOWS:
        rect = _RECT()
        if _user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
            return (rect.left, rect.top, rect.right, rect.bottom)
    left, top, width, height = virtual_screen_rect()
    return (left, top, left + width, top + height)


def clamp_to_visible(
    x: int, y: int, width: int, height: int, margin: int = 0
) -> tuple[int, int]:
    """Keep a window fully inside the virtual desktop when possible."""
    left, top, screen_width, screen_height = virtual_screen_rect()
    right, bottom = left + screen_width, top + screen_height

    if margin > 0:
        left += margin
        top += margin
        right -= margin
        bottom -= margin
        if right <= left or bottom <= top:
            left, top, screen_width, screen_height = virtual_screen_rect()
            right, bottom = left + screen_width, top + screen_height

    if width >= right - left:
        x = left
    else:
        x = max(left, min(int(x), right - width))
    if height >= bottom - top:
        y = top
    else:
        y = max(top, min(int(y), bottom - height))
    return (x, y)


def default_position(width: int, height: int, margin: int = 28) -> tuple[int, int]:
    """Place the widget near the top-right of the primary monitor."""
    _left, top, right, _bottom = primary_work_area()
    x = right - width - margin
    y = top + margin
    return clamp_to_visible(x, y, width, height)


def acquire_single_instance(name: str) -> bool:
    """Return True if this is the only running instance."""
    global _single_instance_handle
    if not IS_WINDOWS:
        return True
    handle = _kernel32.CreateMutexW(None, True, name)
    if not handle:
        return True
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(handle)
        return False
    _single_instance_handle = handle
    return True

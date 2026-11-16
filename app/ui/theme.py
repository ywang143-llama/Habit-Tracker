"""Shared colors, dimensions, and fonts."""

from __future__ import annotations

import customtkinter as ctk

# Surfaces
BG = "#15171d"
SURFACE = "#1e2129"
HOVER = "#232731"
BORDER = "#2b303b"
TRACK = "#262a34"

# Type
TEXT = "#eef1f6"
MUTED = "#8b93a4"
FAINT = "#616978"
DONE_TEXT = "#6f7686"

# Accent
ACCENT = "#6d9bf5"
ACCENT_HOVER = "#88aeff"
ON_ACCENT = "#10131a"

# Streak badges
STREAK_BG = "#2c2718"
STREAK_TEXT = "#f3c46a"
STREAK_HOT_BG = "#302220"
STREAK_HOT_TEXT = "#ff9d78"
STREAK_ZERO_BG = "#22252e"
STREAK_ZERO_TEXT = "#6a7283"

# Feedback
DANGER = "#ff8585"
DANGER_BG = "#341f24"
DANGER_HOVER = "#42262c"

FONT_FAMILY = "Segoe UI"
FONT_SYMBOL = "Segoe UI Symbol"

WINDOW_WIDTH = 322
CARD_RADIUS = 20
WINDOW_OPACITY = 0.90
PAD = 18


class Fonts:
    """All fonts in one place; CTkFont needs a root window to exist."""

    def __init__(self) -> None:
        self.title = ctk.CTkFont(family=FONT_FAMILY, size=17, weight="bold")
        self.date = ctk.CTkFont(family=FONT_FAMILY, size=11)
        self.habit = ctk.CTkFont(family=FONT_FAMILY, size=13)
        self.badge = ctk.CTkFont(family=FONT_FAMILY, size=10, weight="bold")
        self.meta = ctk.CTkFont(family=FONT_FAMILY, size=11)
        self.body = ctk.CTkFont(family=FONT_FAMILY, size=12)
        self.section = ctk.CTkFont(family=FONT_FAMILY, size=15, weight="bold")
        self.empty_title = ctk.CTkFont(family=FONT_FAMILY, size=13, weight="bold")
        self.small = ctk.CTkFont(family=FONT_FAMILY, size=10)
        self.icon = ctk.CTkFont(family=FONT_SYMBOL, size=15)
        self.close = ctk.CTkFont(family=FONT_FAMILY, size=16)
        self.button = ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold")

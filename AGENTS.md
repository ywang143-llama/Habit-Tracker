# Habit Tracker — Agent Guide

A lightweight, frameless Windows desktop habit tracker with a tray menu and local
JSON storage. Source is Python; releases are self-contained PyInstaller
executables with a Desktop shortcut.

## Commands

```powershell
conda activate base
python -m pip install -r requirements.txt

pythonw main.py                      # run without a console
python main.py                       # run with logs in the console

python -m unittest discover -s tests -t . -v
python -m ruff check --select F,E9 main.py app tests

python -m pip install pyinstaller
.\build.ps1                          # dist\Habit Tracker.exe
.\build.ps1 -Install                 # build + install + refresh Desktop shortcut
```

The app targets Windows 10/11 and Python 3.10+. The development environment on
this machine is conda `base`.

## Data

- Source run: `config.json` and `habits.json` next to `main.py`, if writable.
- Frozen exe: the exe's own folder if writable; otherwise
  `%LOCALAPPDATA%\HabitTracker`.
- `HABIT_TRACKER_HOME` overrides the data folder.
- `config.json`: `x`, `y`, `always_on_top`.
- `habits.json`: `version` plus an ordered list of
  `id` / `name` / `created` / `history` records. The list order is the UI order.
- Never commit `config.json`, `habits.json`, `habit_tracker.log`,
  `*.corrupt-*.json`, `build/`, `dist/`, or `*.spec`. `.gitignore` covers these.

## Architecture

```
main.py                  dependency check, logging, DPI awareness,
                         single-instance mutex, app startup
app/controller.py        TrackerApp: store ownership, tray thread bridge,
                         visibility, topmost/startup toggles, shutdown
app/tray.py              pystray icon and menu
app/icon.py              runtime tray icon drawing (Pillow)
app/config.py            ConfigStore
app/habits.py            Habit, streak calculation, HabitStore (+ move)
app/storage.py           atomic JSON writes, BOM-tolerant reads, quarantine
app/paths.py             data/asset locations for source and frozen builds
app/startup.py           shell:startup .lnk creation/removal via PowerShell
app/win.py               DPI, toolwindow style, rounded region, screen bounds
app/ui/widget.py         CTk root, header controls, habit list, footer,
                         reorder orchestration
app/ui/habit_row.py      one row: check, name, streak badge, drag events
app/ui/settings.py       frameless add/remove modal
app/ui/controls.py       CheckCircle, drag-to-move-window, ellipsize, no-drag
app/ui/theme.py          colors, dimensions, fonts
build.ps1                PyInstaller build and optional install
```

## Important invariants

- **Tk runs only on the main thread.** Tray callbacks enqueue actions;
  `TrackerApp._pump_commands` executes them on the Tk thread every 60 ms.
- **Never store data in PyInstaller's `_MEIPASS`.** It is a temporary extraction
  folder. Use `app.paths.data_dir()`.
- **Enable DPI awareness before Tk starts.** `win.enable_dpi_awareness()` is
  called in `main.py`; CustomTkinter otherwise enables it too late.
- **Spacing units differ.** CustomTkinter scales `pack`/`grid`/`place` padding
  itself, so pass design units (e.g. `padx=(8, 8)`). Use physical pixels only for
  raw `tk.Canvas`/`tk.Frame` geometry and Win32 calls.
- **Rows must stay draggable without moving the window.** Habit rows are marked
  with `mark_no_drag`; drag-to-move-window checks that marker up the widget chain.
- **Data writes are atomic.** All JSON goes through `app.storage.write_json_atomic`.
  Corrupt habit files are quarantined instead of overwritten.
- **Midnight rollover is date-derived.** `FloatingWidget._check_day` polls every
  20 s; changing `_today` rebuilds rows and clears completed checkboxes.
- **Window chrome is native.** The card is `overrideredirect`, alpha 0.9, clipped
  with `SetWindowRgn`, and hidden from the taskbar/Alt+Tab using
  `WS_EX_TOOLWINDOW`. CTk's DWM titlebar manipulation is disabled on the root and
  the settings modal.
- **Tray menu state is refreshed explicitly** after visibility, topmost, and
  startup changes because pystray caches the native menu.
- **The installed exe has its own data.** A source run and an installed run do
  not share config/habits unless `HABIT_TRACKER_HOME` points both at the same
  folder.

## Habit reordering

- Drag a row's background, name, or streak badge up/down. A 6-design-pixel
  vertical threshold separates a click (toggle completion) from a drag.
- The check circle remains an immediate toggle and does not initiate reordering.
- `HabitRow` reports `on_reorder_start/move/end` to `FloatingWidget`. The parent
  computes the insertion slot from the row centers, sets the target index, and
  shows a blue `tk.Frame` insertion line inside the scrollable list.
- On release, `HabitStore.move()` reorders the in-memory list, `_save_habits()`
  persists it, and `_repack_rows()` repacks the existing row widgets instead of
  rebuilding them, preserving the list's scroll offset (restored with
  `after_idle`).
- The new order is part of `habits.json` and survives restarts. The settings
  modal reads the same ordered list.
- There is no auto-scroll while dragging yet. Reordering within the visible list
  is supported; for long lists, scroll first, then drag.
- Tests: `test_move_reorders_and_persists` covers the store. The UI drag can be
  exercised by generating `<ButtonPress-1>` / `<B1-Motion>` /
  `<ButtonRelease-1>` on `row._canvas` with `rootx`/`rooty` coordinates.

## Build / release

- PyInstaller one-file, windowed, no console. `build.ps1` bundles `assets/`,
  `customtkinter`, and explicitly adds conda's Tcl/Tk, libffi, OpenSSL, lzma, and
  bz2 DLLs from `Library\bin`. `numpy` is excluded to keep the exe small.
- `-Install` stops if the app is running, copies the exe to
  `%LOCALAPPDATA%\Programs\Habit Tracker\Habit Tracker.exe`, and creates
  `Habit Tracker.lnk` on the Desktop. Existing habit data is left alone.
- The frozen app's startup shortcut points at the exe itself, never at an asset
  inside the one-file `_MEIPASS` folder.
- Re-run `.\build.ps1 -Install` after changing application code so the installed
  program and Desktop shortcut use the new build.

## Git

The project is its own repository (`main`, remote `origin` on GitHub). Commit
source, tests, docs, and build scripts only; do not commit runtime data, build
outputs, or the installed/Desktop shortcut. Push only when the user asks.

## UI conventions

- Colors, radii, opacity, fonts, and the 322-design-px card width live in
  `app/ui/theme.py`.
- Keep the card quiet: muted metadata, one accent color, amber/orange streak
  badges, danger tint only on destructive hover.
- Check circles are custom `tk.Canvas` widgets; keep their background synced
  with row hover states.
- Long habit names are truncated with `ellipsize` so the card width stays fixed.
- The header order is gear, minimize, close. Minimize hides to tray; close quits
  via `TrackerApp.quit`.

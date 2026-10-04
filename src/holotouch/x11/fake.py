"""In-memory window backend for tests and --dry-run. Records every command it receives."""

from __future__ import annotations

import logging

from holotouch.core.actions import ALL_DESKTOPS, WindowInfo

log = logging.getLogger(__name__)


class FakeBackend:
    def __init__(self, screen: tuple[int, int] = (2880, 1800), desktops: int = 4, verbose: bool = False):
        self._screen = screen
        self._desktops = desktops
        self._current = 0
        self._stack: list[WindowInfo] = []  # bottom to top
        self._restore: dict[int, tuple[int, int, int, int]] = {}
        self._active: int | None = None
        self._pointer = (0, 0)
        self.verbose = verbose
        self.commands: list[tuple] = []
        self.scrolled = 0.0
        self.dials: dict[str, float | None] = {"volume": 0.5, "brightness": 0.5}

    def _record(self, *command) -> None:
        self.commands.append(command)
        if self.verbose:
            log.info("dry-run: %s", command)

    def add_window(self, win: WindowInfo) -> WindowInfo:
        self._stack.append(win)
        return win

    def replace_windows(self, *windows: WindowInfo) -> None:
        """Start again with just these windows, bottom to top."""
        self._stack = list(windows)
        self._restore.clear()
        self._active = None

    # -- WindowBackend ---------------------------------------------------------------------

    def screen_size(self) -> tuple[int, int]:
        return self._screen

    def workarea(self) -> tuple[int, int, int, int]:
        return (0, 0, *self._screen)

    def poll(self) -> None:
        pass

    def flush(self) -> None:
        pass

    def _visible(self, win: WindowInfo) -> bool:
        return not win.minimized and win.desktop in (self._current, ALL_DESKTOPS)

    def windows(self) -> list[WindowInfo]:
        return [w for w in reversed(self._stack) if self._visible(w)]

    def all_windows(self) -> list[WindowInfo]:
        return list(reversed(self._stack))

    def window_at(self, x: float, y: float) -> WindowInfo | None:
        return next((w for w in self.windows() if w.contains(x, y)), None)

    def get(self, win_id: int) -> WindowInfo | None:
        return next((w for w in self._stack if w.id == win_id), None)

    def active_window(self) -> WindowInfo | None:
        return self.get(self._active) if self._active is not None else None

    def activate(self, win_id: int) -> None:
        self._record("activate", win_id)
        win = self.get(win_id)
        if win is not None:
            self._stack.remove(win)
            self._stack.append(win)
            win.minimized = False
            self._active = win_id

    def move_resize(self, win_id: int, x: int, y: int, w: int, h: int) -> None:
        self._record("move_resize", win_id, x, y, w, h)
        win = self.get(win_id)
        if win is not None and not win.maximized:
            win.x, win.y, win.w, win.h = x, y, w, h

    def set_maximized(self, win_id: int, on: bool) -> None:
        self._record("set_maximized", win_id, on)
        win = self.get(win_id)
        if win is None or win.maximized == on:
            return
        if on:
            self._restore[win_id] = (win.x, win.y, win.w, win.h)
            win.x, win.y, win.w, win.h = self.workarea()
        else:
            win.x, win.y, win.w, win.h = self._restore.pop(win_id, (100, 100, 800, 600))
        win.maximized = on

    def minimize(self, win_id: int) -> None:
        self._record("minimize", win_id)
        win = self.get(win_id)
        if win is not None:
            win.minimized = True
            if self._active == win_id:
                self._active = next((w.id for w in self.windows()), None)

    def close(self, win_id: int) -> None:
        self._record("close", win_id)
        win = self.get(win_id)
        if win is not None:
            self._stack.remove(win)

    def desktop_count(self) -> int:
        return self._desktops

    def current_desktop(self) -> int:
        return self._current

    def switch_desktop(self, index: int) -> None:
        self._record("switch_desktop", index)
        self._current = index

    def set_window_desktop(self, win_id: int, index: int) -> None:
        self._record("set_window_desktop", win_id, index)
        win = self.get(win_id)
        if win is not None:
            win.desktop = index

    def pointer_pos(self) -> tuple[int, int]:
        return self._pointer

    def warp_pointer(self, x: int, y: int) -> None:
        self._record("warp_pointer", x, y)
        self._pointer = (x, y)

    def scroll(self, notches: float) -> None:
        self.scrolled += notches

    def dial(self, name: str) -> float | None:
        return self.dials[name]

    def set_dial(self, name: str, level: float) -> None:
        self.dials[name] = level
        self._record(f"set_{name}", round(level, 2))

    def button_down(self, x: int, y: int) -> None:
        self._record("button_down", x, y)

    def pointer_to(self, x: int, y: int) -> None:
        self._record("pointer_to", x, y)

    def button_up(self) -> None:
        self._record("button_up")

    def press_key(self, key: str) -> None:
        self._record("press_key", key)

    def type_text(self, text: str) -> None:
        self._record("type_text", text)

    def skip_track(self, direction: int) -> None:
        self._record("skip_track", direction)

    def play_pause(self) -> None:
        self._record("play_pause")

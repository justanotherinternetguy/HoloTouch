"""The window-manager interface the interaction engine drives.

The engine only talks to this protocol, so it runs the same against the real X11 backend and the
in-memory fake used by tests and --dry-run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

ALL_DESKTOPS = -1


@dataclass(slots=True)
class WindowInfo:
    id: int
    # Visible frame rectangle in root pixels (decorations included, CSD shadows excluded).
    x: int
    y: int
    w: int
    h: int
    desktop: int = 0
    title: str = ""
    wm_class: str = ""
    maximized: bool = False
    fullscreen: bool = False
    minimized: bool = False
    min_w: int = 1
    min_h: int = 1

    def contains(self, px: float, py: float) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h


@dataclass(slots=True)
class Pixels:
    """A small image as 32-bit pixels: blue, green, red, alpha (not premultiplied)."""

    w: int
    h: int
    data: bytes


class WindowBackend(Protocol):
    def screen_size(self) -> tuple[int, int]: ...
    def workarea(self) -> tuple[int, int, int, int]: ...
    def poll(self) -> None: ...
    def flush(self) -> None: ...

    def windows(self) -> list[WindowInfo]: ...  # current workspace, topmost first
    def all_windows(self) -> list[WindowInfo]: ...  # every workspace, minimized ones too
    def window_at(self, x: float, y: float) -> WindowInfo | None: ...
    def get(self, win_id: int) -> WindowInfo | None: ...
    def active_window(self) -> WindowInfo | None: ...

    def activate(self, win_id: int) -> None: ...
    def move_resize(self, win_id: int, x: int, y: int, w: int, h: int) -> None: ...
    def set_maximized(self, win_id: int, on: bool) -> None: ...
    def minimize(self, win_id: int) -> None: ...
    def close(self, win_id: int) -> None: ...

    def desktop_count(self) -> int: ...
    def current_desktop(self) -> int: ...
    def switch_desktop(self, index: int) -> None: ...
    def set_window_desktop(self, win_id: int, index: int) -> None: ...

    def pointer_pos(self) -> tuple[int, int]: ...
    def warp_pointer(self, x: int, y: int) -> None: ...
    def scroll(self, notches: float) -> None: ...  # positive scrolls up
    # A dial is "volume" or "brightness"; its level runs 0..1, and is None if it cannot be read.
    def dial(self, name: str) -> float | None: ...
    def set_dial(self, name: str, level: float) -> None: ...
    # The left mouse button: pressed at a point on the screen, the pointer taken elsewhere while
    # it is down, and let go. The pointer stays where it ends up.
    def button_down(self, x: int, y: int) -> None: ...
    def pointer_to(self, x: int, y: int) -> None: ...
    def button_up(self) -> None: ...
    # One character, space or Return, typed into the active window: with Control, Shift or Alt
    # held when it is given as "ctrl+t".
    def press_key(self, key: str) -> None: ...
    def type_text(self, text: str) -> None: ...  # typed, as if at the keyboard, into whatever has it
    def skip_track(self, direction: int) -> None: ...  # 1 the next track of whatever is playing, -1 the one before

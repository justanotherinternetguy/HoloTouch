"""The window backend for GNOME under Wayland: the windows as HoloTouch's Shell extension reports them.

Wayland lets no program but the compositor list windows, move them or press keys, so all of that
is asked of an extension inside GNOME Shell (extension/extension.js), over the session bus. The
extension sends the state of the desktop whenever it changes, and what is kept here is the last
state it sent.

GNOME Shell counts in its own units, which on a scaled monitor are not the pixels the overlay
draws in: the overlay is an X11 window, shown by XWayland. Everything is converted on its way in
and out, so the engine sees only the overlay's pixels.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from holotouch.core.actions import ALL_DESKTOPS, Pixels, WindowInfo
from holotouch.keys import keysyms
from holotouch.system import SystemControls

log = logging.getLogger(__name__)

VERSION = 1  # of the extension's interface: the VERSION in extension/extension.js
_RESYNC_INTERVAL_S = 2.0
_START_S = 3.0  # how long GNOME Shell has to answer when the backend starts
_THUMBNAILS_S = 2.0  # how long it has to make the switcher's pictures
_RESTORE_S = 0.3  # how long a window let out of maximize has to take its old size


class ShellMissing(ValueError):
    """The extension does not answer, or is not the one this HoloTouch works with."""


class ShellScroller:
    """Scrolling by GNOME Shell's own virtual pointer: any part of a wheel notch, so it is smooth."""

    def __init__(self, link):
        self._link = link

    def scroll(self, notches: float) -> None:
        if notches:
            self._link.send("Scroll", "d", float(notches))

    def close(self) -> None:
        pass


def _make_scroller(mode: str, link):
    if mode == "uinput":
        from holotouch.x11.input import UinputScroller

        return UinputScroller()
    return ShellScroller(link)


class GnomeBackend(SystemControls):
    def __init__(self, scroll_backend: str = "auto", screen: tuple[int, int] | None = None, link=None):
        """`screen` is the size of what the overlay covers, in its own pixels; GNOME Shell's, if not given."""
        if link is None:
            from holotouch.gnome.shell import ShellLink

            try:
                link = ShellLink()
            except Exception as exc:  # no session bus at all
                raise ShellMissing(f"cannot reach the session bus: {exc}") from exc
        self._link = link
        answer = link.ask("Watch", timeout=_START_S)
        if answer is None:
            raise ShellMissing(
                "HoloTouch's GNOME Shell extension does not answer. Run `holotouch gnome` to install it, "
                "then log out and back in: GNOME Shell only finds a new extension when it starts."
            )
        state = json.loads(answer[0])
        if state.get("version") != VERSION:
            raise ShellMissing(
                f"GNOME Shell is running version {state.get('version')} of HoloTouch's extension and this "
                f"HoloTouch works with version {VERSION}. Run `holotouch gnome`, then log out and back in."
            )
        stage = state["size"]
        self._screen = tuple(screen) if screen else (stage[0], stage[1])
        self._scale = self._screen[0] / stage[0]  # overlay pixels to one of GNOME Shell's units
        if self._scale != 1.0:
            log.info("GNOME Shell counts %d x %d; the overlay draws %d x %d", *stage, *self._screen)
        self._windows: dict[int, WindowInfo] = {}
        self._extras: dict[int, tuple[bool, str]] = {}  # window -> kept off the taskbar, its icon's name
        self._stacking: list[int] = []  # bottom to top
        self._current = 0
        self._count = 1
        self._active = 0
        self._workarea = (0, 0, *self._screen)
        self._pointer = (0, 0)
        self._restoring: dict[int, tuple[tuple[int, int, int, int], float]] = {}  # window -> its maximized place, and when to stop waiting
        self._button_down = False
        self._last_resync = time.monotonic()
        self._scroller = _make_scroller(scroll_backend, link)
        self._apply(state)

    # -- model -------------------------------------------------------------------------------

    def _in(self, value: float) -> int:
        return round(value * self._scale)

    def _out(self, value: float) -> int:
        return round(value / self._scale)

    def _apply(self, state: dict) -> None:
        screen_w, screen_h = self._screen
        windows, extras, stacking = {}, {}, []
        for w in state["windows"]:
            min_w, min_h = w.get("min", (1, 1))
            windows[w["id"]] = WindowInfo(
                id=w["id"],
                x=self._in(w["x"]),
                y=self._in(w["y"]),
                w=self._in(w["w"]),
                h=self._in(w["h"]),
                desktop=ALL_DESKTOPS if w["workspace"] < 0 else w["workspace"],
                title=w["title"],
                wm_class=w["class"],
                maximized=w["maximized"],
                fullscreen=w["fullscreen"],
                minimized=w["minimized"],
                # A window that names no least size is given as none, or as a nonsense one.
                min_w=min(max(self._in(min_w), 1), screen_w),
                min_h=min(max(self._in(min_h), 1), screen_h),
            )
            extras[w["id"]] = (bool(w.get("skip")), w.get("icon", ""))
            stacking.append(w["id"])
        # A window let out of maximize is said to be out at once, and only then asked to take its
        # old size, which it does in its own time. Until it has, it still counts as maximized, so
        # that nobody takes the size of the screen for the size it goes back to.
        now = time.monotonic()
        for win, (rect, deadline) in list(self._restoring.items()):
            info = windows.get(win)
            if info is None or info.maximized or (info.x, info.y, info.w, info.h) != rect or now > deadline:
                del self._restoring[win]
            else:
                info.maximized = True
        self._windows, self._extras, self._stacking = windows, extras, stacking
        self._current = state["workspace"]
        self._count = state["workspaces"]
        self._active = state["active"]
        self._workarea = tuple(self._in(v) for v in state["workarea"])

    def _apply_json(self, state: str) -> None:
        try:
            self._apply(json.loads(state))
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("GNOME Shell sent a state that cannot be read: %s", exc)

    def poll(self) -> None:
        self._apply_volume()
        for name, body in self._link.poll():
            if name == "StateChanged":
                self._apply_json(body[0])
        now = time.monotonic()
        if now - self._last_resync > _RESYNC_INTERVAL_S:
            # GNOME Shell turns its extensions off while the screen is locked, and forgets who was
            # watching: asking again puts that right, and makes up for any signal that was missed.
            self._last_resync = now
            self._link.ask_later("Watch", self._apply_json)

    def flush(self) -> None:
        pass  # nothing is held back

    # -- queries -----------------------------------------------------------------------------

    def screen_size(self) -> tuple[int, int]:
        return self._screen

    def workarea(self) -> tuple[int, int, int, int]:
        return self._workarea

    def windows(self) -> list[WindowInfo]:
        result = []
        for win in reversed(self._stacking):
            info = self._windows[win]
            if not info.minimized and info.desktop in (self._current, ALL_DESKTOPS):
                result.append(info)
        return result

    def all_windows(self) -> list[WindowInfo]:
        return [self._windows[win] for win in reversed(self._stacking) if not self._extras[win][0]]

    def window_at(self, x: float, y: float) -> WindowInfo | None:
        return next((w for w in self.windows() if w.contains(x, y)), None)

    def get(self, win_id: int) -> WindowInfo | None:
        return self._windows.get(win_id)

    def active_window(self) -> WindowInfo | None:
        """The focused application window. Focus on GNOME Shell itself counts as none."""
        info = self._windows.get(self._active)
        return info if info is not None and not info.minimized else None

    def window_icon(self, win_id: int, size: int) -> Pixels | None:
        """The icon of the window's app, at about `size` pixels."""
        name = self._extras.get(win_id, (False, ""))[1]
        if not name:
            return None
        from PySide6.QtGui import QIcon

        icon = QIcon(name) if name.startswith("/") else QIcon.fromTheme(name)
        return _pixels(icon.pixmap(size, size).toImage())

    def window_thumbnails(self, win_ids: list[int], max_w: int, max_h: int) -> dict[int, Pixels]:
        """Pictures of the windows, scaled to fit max_w x max_h: also of those minimized or on another workspace."""
        ids = [win for win in win_ids if win in self._windows]
        answer = self._link.ask("Thumbnails", "atii", ids, max_w, max_h, timeout=_THUMBNAILS_S) if ids else None
        if answer is None:
            return {}
        from PySide6.QtGui import QImage

        result = {}
        for win, path in json.loads(answer[0]).items():
            pixels = _pixels(QImage(path))
            Path(path).unlink(missing_ok=True)
            if pixels is not None:
                result[int(win)] = pixels
        return result

    def desktop_count(self) -> int:
        return self._count

    def current_desktop(self) -> int:
        return self._current

    # -- commands ----------------------------------------------------------------------------

    def activate(self, win_id: int) -> None:
        self._link.send("Activate", "t", win_id)

    def move_resize(self, win_id: int, x: int, y: int, w: int, h: int) -> None:
        if win_id in self._windows:
            self._link.send(
                "MoveResize", "tiiii", win_id, self._out(x), self._out(y), max(self._out(w), 1), max(self._out(h), 1)
            )

    def set_maximized(self, win_id: int, on: bool) -> None:
        info = self._windows.get(win_id)
        if info is not None and info.maximized and not on:
            self._restoring[win_id] = ((info.x, info.y, info.w, info.h), time.monotonic() + _RESTORE_S)
        self._link.send("SetMaximized", "tb", win_id, on)

    def minimize(self, win_id: int) -> None:
        self._link.send("Minimize", "t", win_id)

    def close(self, win_id: int) -> None:
        self._link.send("Close", "t", win_id)

    def switch_desktop(self, index: int) -> None:
        self._link.send("SwitchWorkspace", "i", index)
        self._current = index  # optimistic; confirmed by the next state

    def set_window_desktop(self, win_id: int, index: int) -> None:
        self._link.send("SetWindowWorkspace", "ti", win_id, index)

    def pointer_pos(self) -> tuple[int, int]:
        answer = self._link.ask("Pointer", timeout=0.25)
        if answer is not None:
            self._pointer = (self._in(answer[0]), self._in(answer[1]))
        return self._pointer

    def warp_pointer(self, x: int, y: int) -> None:
        self._pointer = (x, y)
        self._link.send("WarpPointer", "dd", x / self._scale, y / self._scale)

    def scroll(self, notches: float) -> None:
        self._scroller.scroll(notches)

    # The pointer goes there and, unlike for scrolling, stays: taking it away between two clicks
    # keeps some programs from seeing a double click, and menus opened by a click follow it.
    def button_down(self, x: int, y: int) -> None:
        if self._button_down:
            return
        self._button_down = True
        self.warp_pointer(x, y)
        self._link.send("Button", "b", True)

    def pointer_to(self, x: int, y: int) -> None:
        self.warp_pointer(x, y)

    def button_up(self) -> None:
        if self._button_down:
            self._button_down = False
            self._link.send("Button", "b", False)

    def press_key(self, key: str) -> None:
        wanted = keysyms(key)
        if None in wanted:
            log.warning("%r names no key", key)
            return
        self._link.send("Keys", "au", wanted)

    def type_text(self, text: str) -> None:
        self._link.send("TypeText", "s", text)

    # The clipboard cannot be read from outside the compositor either, so sending a page to the
    # phone, which copies the page's address, reads it through here.
    def clipboard(self) -> tuple[str | None, str | None]:
        """The clipboard's text, and a number that changes whenever something is copied; each None if it cannot be had."""
        answer = self._link.ask("GetClipboard", timeout=0.5)
        if answer is None:
            return None, None
        has_text, text, serial = answer
        return (text if has_text else None), str(serial)

    def set_clipboard(self, text: str) -> None:
        self._link.send("SetClipboard", "s", text)

    def close_backend(self) -> None:
        self.button_up()  # a button left down would stay down after we are gone
        self._scroller.close()
        self._link.send("Unwatch")
        self._link.close()


def _pixels(image) -> Pixels | None:
    """A QImage as the overlay takes pictures."""
    from PySide6.QtGui import QImage

    if image.isNull():
        return None
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    data = bytes(image.constBits())
    if image.bytesPerLine() != image.width() * 4:  # rows padded out: not with four bytes a pixel, but to be sure
        stride = image.bytesPerLine()
        data = b"".join(data[row * stride : row * stride + image.width() * 4] for row in range(image.height()))
    return Pixels(image.width(), image.height(), data)

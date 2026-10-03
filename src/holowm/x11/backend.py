"""The real window backend: a cached model of xfwm4's windows plus EWMH requests to change them."""

from __future__ import annotations

import logging
import re
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass

import xcffib.xproto as xp

from holowm.core.actions import ALL_DESKTOPS, Pixels, WindowInfo
from holowm.x11.conn import X11
from holowm.x11.images import WindowImager
from holowm.x11.input import make_scroller, press_button, press_key

log = logging.getLogger(__name__)

_SOURCE_PAGER = 2
_GRAVITY_NORTH_WEST = 1
_MOVERESIZE_FLAGS = _GRAVITY_NORTH_WEST | (0b1111 << 8) | (_SOURCE_PAGER << 12)
_ICONIC_STATE = 3
_RESYNC_INTERVAL_S = 2.0
_CLIENT_EVENTS = xp.EventMask.StructureNotify | xp.EventMask.PropertyChange
_ROOT_PROPERTIES = (
    "_NET_CURRENT_DESKTOP",
    "_NET_NUMBER_OF_DESKTOPS",
    "_NET_ACTIVE_WINDOW",
    "_NET_WORKAREA",
)
_PROPERTIES = (
    "_NET_FRAME_EXTENTS",
    "_GTK_FRAME_EXTENTS",
    "_NET_WM_DESKTOP",
    "_NET_WM_STATE",
    "_NET_WM_WINDOW_TYPE",
    "WM_NORMAL_HINTS",
    "_NET_WM_NAME",
    "WM_NAME",
    "WM_CLASS",
)


@dataclass(slots=True)
class _Client:
    info: WindowInfo
    frame: tuple[int, int, int, int]  # decoration sizes: left, right, top, bottom
    shadow: tuple[int, int, int, int]  # client-side shadow margins: left, right, top, bottom
    normal: bool  # an application window, as opposed to a panel or the desktop
    targetable: bool  # a normal, visible window (not a panel, the desktop, or minimized)
    switchable: bool  # a normal window on any workspace, minimized or not
    visual: int
    size: tuple[int, int]  # of the client window, shadows included


class X11Backend:
    def __init__(self, scroll_backend: str = "auto", display: str | None = None):
        self.x = X11(display)
        x = self.x
        x.core.ChangeWindowAttributes(x.root, xp.CW.EventMask, [xp.EventMask.PropertyChange])
        self._clients: dict[int, _Client] = {}
        self._stacking: list[int] = []  # bottom to top
        self._dirty: set[int] = set()
        self._stack_dirty = True
        self._root_dirty = True
        self._current = 0
        self._count = 1
        self._active = 0
        self._workarea = (0, 0, x.screen.width_in_pixels, x.screen.height_in_pixels)
        self._last_resync = 0.0
        self._scroller = make_scroller(scroll_backend, x)
        self._imager = WindowImager(x)
        self._icon_atom = x.atom("_NET_WM_ICON")
        self._icons: dict[tuple[int, int], Pixels | None] = {}  # (window, size) -> icon
        self._atom_names = {x.atom(n): n for n in _ROOT_PROPERTIES + ("_NET_CLIENT_LIST_STACKING",)}
        self._state_atoms = {
            name: x.atom(name)
            for name in (
                "_NET_WM_STATE_MAXIMIZED_VERT",
                "_NET_WM_STATE_MAXIMIZED_HORZ",
                "_NET_WM_STATE_FULLSCREEN",
                "_NET_WM_STATE_HIDDEN",
                "_NET_WM_STATE_SKIP_TASKBAR",
                "_NET_WM_WINDOW_TYPE_DOCK",
                "_NET_WM_WINDOW_TYPE_DESKTOP",
            )
        }
        self._sync()

    # -- model -------------------------------------------------------------------------------

    def poll(self) -> None:
        self._apply_volume()
        for event in self.x.events():
            if isinstance(event, xp.PropertyNotifyEvent):
                if event.window == self.x.root:
                    name = self._atom_names.get(event.atom)
                    if name == "_NET_CLIENT_LIST_STACKING":
                        self._stack_dirty = True
                    elif name is not None:
                        self._root_dirty = True
                elif event.window in self._clients:
                    self._dirty.add(event.window)
                    if event.atom == self._icon_atom:
                        self._drop_icons(event.window)
            elif isinstance(event, (xp.ConfigureNotifyEvent, xp.MapNotifyEvent)):
                if event.window in self._clients:
                    self._dirty.add(event.window)
            elif isinstance(event, (xp.DestroyNotifyEvent, xp.UnmapNotifyEvent)):
                if event.window in self._clients:
                    self._dirty.add(event.window)
        now = time.monotonic()
        if now - self._last_resync > _RESYNC_INTERVAL_S:
            # Safety net in case an event was missed.
            self._last_resync = now
            self._stack_dirty = self._root_dirty = True
            self._dirty.update(self._clients)

    def _sync(self) -> None:
        x = self.x
        if self._root_dirty:
            self._root_dirty = False
            cookies = [x.get_property(x.root, name) for name in _ROOT_PROPERTIES]
            current, count, active, workarea = (x.cardinals(x.reply(c)) for c in cookies)
            self._current = current[0] if current else 0
            self._count = count[0] if count else 1
            self._active = active[0] if active else 0
            if len(workarea) >= 4:
                offset = 4 * self._current if len(workarea) >= 4 * (self._current + 1) else 0
                self._workarea = tuple(workarea[offset : offset + 4])
        if self._stack_dirty:
            self._stack_dirty = False
            stacking = x.cardinals(x.reply(x.get_property(x.root, "_NET_CLIENT_LIST_STACKING")))
            for win in stacking:
                if win not in self._clients:
                    x.core.ChangeWindowAttributes(win, xp.CW.EventMask, [_CLIENT_EVENTS])
                    self._dirty.add(win)
            for win in set(self._clients) - set(stacking):
                del self._clients[win]
                self._drop_icons(win)
            self._dirty &= set(stacking)
            self._stacking = stacking
        if self._dirty:
            dirty, self._dirty = self._dirty, set()
            queries = {win: self._query(win) for win in dirty}
            for win, query in queries.items():
                client = self._read(win, query)
                if client is None:
                    self._clients.pop(win, None)
                else:
                    self._clients[win] = client

    def _query(self, win: int):
        core = self.x.core
        return (
            core.GetGeometry(win),
            core.TranslateCoordinates(win, self.x.root, 0, 0),
            core.GetWindowAttributes(win),
            [self.x.get_property(win, name) for name in _PROPERTIES],
        )

    def _read(self, win: int, query) -> _Client | None:
        x = self.x
        geometry, origin, attributes = (x.reply(c) for c in query[:3])
        frame, shadow, desktop, state, types, hints, name, legacy_name, wm_class = (x.reply(c) for c in query[3])
        if geometry is None or origin is None or attributes is None:
            return None
        atoms = self._state_atoms
        fl, fr, ft, fb = (x.cardinals(frame) + [0, 0, 0, 0])[:4]
        sl, sr, st, sb = (x.cardinals(shadow) + [0, 0, 0, 0])[:4]
        states = set(x.cardinals(state))
        kinds = set(x.cardinals(types))
        desktops = x.cardinals(desktop)
        desktop_index = desktops[0] if desktops else 0
        min_w = min_h = 1
        normal = x.cardinals(hints)
        if len(normal) >= 7 and normal[0] & (1 << 4):  # PMinSize
            min_w, min_h = normal[5], normal[6]
        elif len(normal) >= 17 and normal[0] & (1 << 8):  # PBaseSize
            min_w, min_h = normal[15], normal[16]
        class_parts = x.text(wm_class).split("\0")
        info = WindowInfo(
            id=win,
            x=origin.dst_x - fl + sl,
            y=origin.dst_y - ft + st,
            w=geometry.width + fl + fr - sl - sr,
            h=geometry.height + ft + fb - st - sb,
            desktop=ALL_DESKTOPS if desktop_index == 0xFFFFFFFF else desktop_index,
            title=x.text(name) or x.text(legacy_name),
            wm_class=class_parts[1] if len(class_parts) > 1 else class_parts[0],
            maximized=atoms["_NET_WM_STATE_MAXIMIZED_VERT"] in states
            and atoms["_NET_WM_STATE_MAXIMIZED_HORZ"] in states,
            fullscreen=atoms["_NET_WM_STATE_FULLSCREEN"] in states,
            minimized=atoms["_NET_WM_STATE_HIDDEN"] in states,
            min_w=max(min_w + fl + fr - sl - sr, 1),
            min_h=max(min_h + ft + fb - st - sb, 1),
        )
        normal = (
            atoms["_NET_WM_WINDOW_TYPE_DOCK"] not in kinds and atoms["_NET_WM_WINDOW_TYPE_DESKTOP"] not in kinds
        )
        return _Client(
            info,
            frame=(fl, fr, ft, fb),
            shadow=(sl, sr, st, sb),
            normal=normal,
            targetable=normal and not info.minimized and attributes.map_state == xp.MapState.Viewable,
            switchable=normal and atoms["_NET_WM_STATE_SKIP_TASKBAR"] not in states,
            visual=attributes.visual,
            size=(geometry.width, geometry.height),
        )

    # -- queries -----------------------------------------------------------------------------

    def screen_size(self) -> tuple[int, int]:
        return self.x.screen.width_in_pixels, self.x.screen.height_in_pixels

    def workarea(self) -> tuple[int, int, int, int]:
        self._sync()
        return self._workarea

    def flush(self) -> None:
        self.x.conn.flush()

    def windows(self) -> list[WindowInfo]:
        self._sync()
        result = []
        for win in reversed(self._stacking):
            client = self._clients.get(win)
            if client and client.targetable and client.info.desktop in (self._current, ALL_DESKTOPS):
                result.append(client.info)
        return result

    def all_windows(self) -> list[WindowInfo]:
        self._sync()
        clients = (self._clients.get(win) for win in reversed(self._stacking))
        return [c.info for c in clients if c and c.switchable]

    def window_at(self, x: float, y: float) -> WindowInfo | None:
        return next((w for w in self.windows() if w.contains(x, y)), None)

    def get(self, win_id: int) -> WindowInfo | None:
        self._sync()
        client = self._clients.get(win_id)
        return client.info if client else None

    def active_window(self) -> WindowInfo | None:
        """The focused application window. Focus on the desktop or a panel counts as none."""
        self._sync()
        client = self._clients.get(self._active)
        return client.info if client is not None and client.targetable else None

    def _drop_icons(self, win: int) -> None:
        for key in [k for k in self._icons if k[0] == win]:
            del self._icons[key]

    def window_icon(self, win_id: int, size: int) -> Pixels | None:
        """The window's own icon, at about `size` pixels."""
        key = (win_id, size)
        if key not in self._icons:
            self._icons[key] = self._imager.icon(win_id, size)
        return self._icons[key]

    def window_thumbnails(self, win_ids: list[int], max_w: int, max_h: int) -> dict[int, Pixels]:
        """Pictures of the windows that are on screen now, scaled to fit max_w x max_h."""
        self._sync()
        sources = []
        for win in win_ids:
            client = self._clients.get(win)
            if client is not None and client.targetable:
                sl, sr, st, sb = client.shadow
                w, h = client.size
                sources.append((win, client.visual, (sl, st, w - sl - sr, h - st - sb)))
        return self._imager.thumbnails(sources, max_w, max_h)

    def desktop_count(self) -> int:
        self._sync()
        return self._count

    def current_desktop(self) -> int:
        self._sync()
        return self._current

    # -- commands ----------------------------------------------------------------------------

    def _normal(self, win_id: int) -> bool:
        """Whether a window may be changed. The window manager would happily minimize or move the
        desktop or a panel if asked, so requests about anything but application windows stop here."""
        client = self._clients.get(win_id)
        return client is not None and client.normal

    def activate(self, win_id: int) -> None:
        self.x.send_root_message(win_id, "_NET_ACTIVE_WINDOW", [_SOURCE_PAGER, self.x.timestamp(), 0])

    def move_resize(self, win_id: int, x: int, y: int, w: int, h: int) -> None:
        client = self._clients.get(win_id)
        if client is None or not client.normal:
            return
        fl, fr, ft, fb = client.frame
        sl, sr, st, sb = client.shadow
        # With north-west gravity the position is the frame's outer corner; the size is the client's.
        self.x.send_root_message(
            win_id,
            "_NET_MOVERESIZE_WINDOW",
            [_MOVERESIZE_FLAGS, x - sl, y - st, max(w - fl - fr + sl + sr, 1), max(h - ft - fb + st + sb, 1)],
        )

    def set_maximized(self, win_id: int, on: bool) -> None:
        if not self._normal(win_id):
            return
        atoms = self._state_atoms
        self.x.send_root_message(
            win_id,
            "_NET_WM_STATE",
            [1 if on else 0, atoms["_NET_WM_STATE_MAXIMIZED_VERT"], atoms["_NET_WM_STATE_MAXIMIZED_HORZ"], _SOURCE_PAGER],
        )

    def minimize(self, win_id: int) -> None:
        if self._normal(win_id):
            self.x.send_root_message(win_id, "WM_CHANGE_STATE", [_ICONIC_STATE])

    def close(self, win_id: int) -> None:
        if self._normal(win_id):
            self.x.send_root_message(win_id, "_NET_CLOSE_WINDOW", [self.x.timestamp(), _SOURCE_PAGER])

    def switch_desktop(self, index: int) -> None:
        self.x.send_root_message(self.x.root, "_NET_CURRENT_DESKTOP", [index, self.x.timestamp()])
        self._current = index  # optimistic; confirmed by the property change

    def set_window_desktop(self, win_id: int, index: int) -> None:
        if self._normal(win_id):
            self.x.send_root_message(win_id, "_NET_WM_DESKTOP", [index, _SOURCE_PAGER])

    def pointer_pos(self) -> tuple[int, int]:
        pointer = self.x.core.QueryPointer(self.x.root).reply()
        return pointer.root_x, pointer.root_y

    def warp_pointer(self, x: int, y: int) -> None:
        self.x.core.WarpPointer(0, self.x.root, 0, 0, 0, 0, x, y)

    def scroll(self, notches: float) -> None:
        self._scroller.scroll(notches)

    def dial(self, name: str) -> float | None:
        return self._brightness() if name == "brightness" else self._volume()

    def set_dial(self, name: str, level: float) -> None:
        if name == "brightness":
            self._set_brightness(level)
        else:
            self._volume_wanted = level
            self._apply_volume()

    @staticmethod
    def _backlight() -> Path | None:
        """The screen's backlight, as the kernel exposes it."""
        return next(iter(sorted(Path("/sys/class/backlight").glob("*"))), None)

    def _brightness(self) -> float | None:
        try:
            device = self._backlight()
            return int((device / "brightness").read_text()) / int((device / "max_brightness").read_text())
        except (OSError, ValueError, TypeError, ZeroDivisionError):
            return None  # no backlight (a desktop monitor, say), or not readable

    def _set_brightness(self, level: float) -> None:
        try:
            device = self._backlight()
            (device / "brightness").write_text(str(round(level * int((device / "max_brightness").read_text()))))
        except (OSError, ValueError, TypeError) as exc:
            log.debug("cannot set the brightness: %s", exc)

    def _volume(self) -> float | None:
        """The default output's volume, as PulseAudio or PipeWire reports it."""
        try:
            out = subprocess.run(
                ["pactl", "get-sink-volume", "@DEFAULT_SINK@"], capture_output=True, text=True, timeout=1
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        percent = re.search(r"(\d+)%", out)
        return int(percent.group(1)) / 100.0 if percent else None

    # The volume is set without waiting, so a slow sound server cannot stall the gesture. A level
    # asked for while the last is still being set is kept, and set from poll() once that is done.
    def _apply_volume(self) -> None:
        wanted = getattr(self, "_volume_wanted", None)
        last = getattr(self, "_volume_call", None)
        if wanted is None or (last is not None and last.poll() is None):
            return
        self._volume_wanted = None
        try:
            self._volume_call = subprocess.Popen(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{round(wanted * 100)}%"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )  # fmt: skip
        except OSError as exc:
            log.debug("cannot set the volume: %s", exc)

    # The pointer goes there and, unlike for scrolling, stays: taking it away between two clicks
    # keeps some programs from seeing a double click, and menus opened by a click follow it.
    def button_down(self, x: int, y: int) -> None:
        if getattr(self, "_button_down", False):
            return
        self._button_down = True
        self.warp_pointer(x, y)
        press_button(self.x, True)

    def pointer_to(self, x: int, y: int) -> None:
        self.warp_pointer(x, y)

    def button_up(self) -> None:
        if getattr(self, "_button_down", False):
            self._button_down = False
            press_button(self.x, False)

    def press_key(self, key: str) -> None:
        if not press_key(self.x, key):
            log.warning("no key on this keyboard types %r", key)

    def skip_track(self, direction: int) -> None:
        # playerctl finds the player last in use. Like the volume, it is not waited for.
        try:
            self._track_call = subprocess.Popen(
                ["playerctl", "next" if direction > 0 else "previous"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )  # fmt: skip
        except OSError as exc:
            log.warning("cannot skip a track: playerctl is needed (%s)", exc.strerror or exc)

    def close_backend(self) -> None:
        self.button_up()  # a button left down would stay down after we are gone
        self.x.conn.flush()
        self._scroller.close()
        self.x.conn.disconnect()

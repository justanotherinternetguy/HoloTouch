"""Which desktop HoloTouch is on, and what follows from that: the backend to use, and how large to draw."""

from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)


def gnome_wayland() -> bool:
    """Whether this is GNOME under Wayland, where windows are reached through GNOME Shell and not the X server."""
    desktops = os.environ.get("XDG_CURRENT_DESKTOP", "").upper().split(":")
    return os.environ.get("XDG_SESSION_TYPE") == "wayland" and "GNOME" in desktops


def x_screen_size() -> tuple[int, int] | None:
    """The size of the X screen, which is what the overlay covers; None if there is no X server."""
    try:
        import xcffib
        import xcffib.xproto  # noqa: F401  (the core protocol, which a connection cannot do without)

        conn = xcffib.connect()
        screen = conn.get_setup().roots[conn.pref_screen]
        size = (screen.width_in_pixels, screen.height_in_pixels)
        conn.disconnect()
        return size
    except Exception as exc:  # no DISPLAY, or nothing answering there
        log.debug("no X server: %s", exc)
        return None


def make_backend(cfg):
    """The backend that changes real windows on this desktop."""
    if gnome_wayland():
        from holotouch.gnome.backend import GnomeBackend

        return GnomeBackend(cfg.gesture.scroll_backend, screen=x_screen_size())
    from holotouch.x11.backend import X11Backend

    return X11Backend(cfg.gesture.scroll_backend)


def _stage_and_scale() -> tuple[int, float] | None:
    """How wide GNOME's desktop is in its own units, and how many screen pixels one of them is on the primary monitor."""
    from jeepney import DBusAddress, new_method_call
    from jeepney.io.blocking import open_dbus_connection

    name = "org.gnome.Mutter.DisplayConfig"
    conn = open_dbus_connection(bus="SESSION")
    try:
        call = new_method_call(DBusAddress("/" + name.replace(".", "/"), bus_name=name, interface=name), "GetCurrentState")
        _, monitors, logical_monitors, properties = conn.send_and_get_reply(call, timeout=2.0).body
    finally:
        conn.close()
    # Each monitor's size in pixels: that of the mode it is in.
    sizes = {}
    for (connector, *_), modes, _ in monitors:
        current = next((mode for mode in modes if "is-current" in mode[6]), None)
        if current is not None:
            sizes[connector] = (current[1], current[2])
    # GNOME counts in pixels divided by the monitor's scale, unless it is laid out in pixels (2).
    in_pixels = properties.get("layout-mode", ("u", 1))[1] == 2
    width, primary_scale = 0, 1.0
    for x, _, scale, transform, primary, shown, _ in logical_monitors:
        size = sizes.get(shown[0][0]) if shown else None
        if size is None:
            continue
        across = size[1] if transform % 2 else size[0]  # turned on its side
        width = max(width, x + round(across if in_pixels else across / scale))
        if primary:
            primary_scale = 1.0 if in_pixels else scale
    return (width, primary_scale) if width else None


def pixel_ratio() -> float:
    """How many of the overlay's pixels make one pixel of the screen. 1 anywhere but on a scaled GNOME desktop.

    Under Wayland the overlay is shown by XWayland, which on a monitor scaled to, say, 133% gives
    X11 programs a screen of twice GNOME's size and scales the result down: half as many pixels
    again as the monitor has. Whatever is drawn has to be that much larger to look the same.
    """
    if not gnome_wayland():
        return 1.0
    try:
        stage = _stage_and_scale()
        screen = x_screen_size()
    except Exception as exc:  # no session bus, or a GNOME that answers otherwise
        log.debug("cannot ask GNOME how the screen is scaled: %s", exc)
        return 1.0
    if stage is None or screen is None:
        return 1.0
    return screen[0] / stage[0] / stage[1]


def adapt(cfg) -> None:
    """Fit a configuration to this desktop: sizes given in pixels are sizes in the screen's own."""
    cfg.ui.scale *= pixel_ratio()

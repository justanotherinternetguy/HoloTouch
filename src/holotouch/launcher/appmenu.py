"""What the pie menu offers for the app in use: that app's own keys, by the kind of app it is.

An app is told by the words of its window class, as the web browsers are for a clap: "Thunar" is
a file manager, "com.mitchellh.ghostty" a terminal, "org.gnome.Nautilus" a file manager again. An app of no kind listed here gets the keys
that mean the same nearly everywhere.

Each kind's items are listed clockwise from the top. Most kinds have seven, which, entered from
where the built-in menu puts them, lie on the compass: the first straight up, the third to the
right, the fifth straight down and the seventh to the left. Two that undo each other, back and
forward, are put opposite each other. The web browser has eight, a little closer together, with
going forward still to the right and going back still to the left.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from holotouch.core.actions import WindowInfo
from holotouch.launcher.menu import MenuItem


def _key(name: str, keys: str, icon: str = "") -> MenuItem:
    return MenuItem(name, "key", keys, icon)


@dataclass(frozen=True)
class AppKind:
    name: str  # what the menu calls it: "This page"
    apps: str  # the apps of this kind, each by a word of its window class
    items: tuple[MenuItem, ...]


BROWSER = AppKind(
    "This page",
    "",  # the browsers are named in the configuration: [gesture] clap_browsers
    (
        MenuItem("Send to phone", "phone", icon="phone"),
        _key("Close tab", "ctrl+w", "window-close"),
        _key("Go forward", "alt+Right", "go-next"),
        _key("Next tab", "ctrl+Tab", "media-skip-forward"),
        _key("Reload", "F5", "view-refresh"),
        _key("Escape", "Escape", "escape"),  # out of a video shown fullscreen, or of a box the page has put up
        _key("Previous tab", "ctrl+shift+Tab", "media-skip-backward"),
        _key("Go back", "alt+Left", "go-previous"),
    ),
)
KINDS = (
    AppKind(
        "This terminal",
        "terminal ghostty kitty alacritty wezterm konsole tilix terminator ptyxis kgx console foot",
        (
            _key("Last command", "Up", "go-up"),
            _key("New tab", "ctrl+shift+t", "plus"),
            _key("Paste", "ctrl+shift+v", "edit-paste"),
            _key("Clear", "ctrl+l", "edit-clear"),
            _key("Interrupt", "ctrl+c", "process-stop"),
            _key("Escape", "Escape", "escape"),
            _key("Copy", "ctrl+shift+c", "edit-copy"),
        ),
    ),
    AppKind(
        "This folder",
        "thunar nautilus nemo dolphin caja pcmanfm",
        (
            _key("Parent folder", "alt+Up", "go-up"),
            _key("New tab", "ctrl+t", "plus"),
            _key("Go forward", "alt+Right", "go-next"),
            _key("Paste", "ctrl+v", "edit-paste"),
            _key("Open", "Return", "enter"),
            _key("Copy", "ctrl+c", "edit-copy"),
            _key("Go back", "alt+Left", "go-previous"),
        ),
    ),
    AppKind(
        "This video",
        "mpv celluloid",
        (
            _key("Fullscreen", "f", "view-fullscreen"),
            _key("Skip ahead", "Up", "media-skip-forward"),  # a minute
            _key("Forward", "Right", "go-next"),  # five seconds
            _key("Mute", "m", "audio-volume-muted"),
            _key("Play / pause", "space", "play"),
            _key("Skip back", "Down", "media-skip-backward"),
            _key("Rewind", "Left", "go-previous"),
        ),
    ),
    AppKind(
        "This video",
        "vlc",
        (
            _key("Fullscreen", "f", "view-fullscreen"),
            _key("Skip ahead", "ctrl+Right", "media-skip-forward"),  # a minute
            _key("Forward", "alt+Right", "go-next"),  # ten seconds
            _key("Mute", "m", "audio-volume-muted"),
            _key("Play / pause", "space", "play"),
            _key("Skip back", "ctrl+Left", "media-skip-backward"),
            _key("Rewind", "alt+Left", "go-previous"),
        ),
    ),
    AppKind(
        "This document",
        "evince atril xreader papers",
        (
            _key("Zoom in", "ctrl+=", "zoom-in"),
            _key("Fullscreen", "F11", "view-fullscreen"),
            _key("Next page", "n", "go-next"),
            _key("Find", "ctrl+f", "edit-find"),
            _key("Zoom out", "ctrl+-", "zoom-out"),
            _key("Fit width", "w", "zoom-fit-best"),
            _key("Previous page", "p", "go-previous"),
        ),
    ),
)
# An app of no kind above: an editor, as likely as not, and these do no harm in anything else.
OTHER = AppKind(
    "This app",
    "",
    (
        _key("Select all", "ctrl+a", "edit-select-all"),
        _key("Save", "ctrl+s", "document-save"),
        _key("Paste", "ctrl+v", "edit-paste"),
        _key("Find", "ctrl+f", "edit-find"),
        _key("Undo", "ctrl+z", "back"),
        _key("Escape", "Escape", "escape"),
        _key("Copy", "ctrl+c", "edit-copy"),
    ),
)


def _words(names: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", names.lower()))


def app_kind(win: WindowInfo | None, browsers: str) -> AppKind:
    """The kind of app a window belongs to; OTHER for one that is of no kind known, and for no window."""
    words = _words(win.wm_class) if win is not None else set()
    if words & _words(browsers):
        return BROWSER
    return next((kind for kind in KINDS if words & _words(kind.apps)), OTHER)

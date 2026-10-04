"""Loads the pie menu, expands dynamic entries, and carries out the chosen item."""

from __future__ import annotations

import copy
import logging
import subprocess
import tomllib
from pathlib import Path

from holotouch.config import MENU_PATH, GestureConfig
from holotouch.core.actions import WindowBackend, WindowInfo
from holotouch.launcher.appmenu import app_kind
from holotouch.launcher.menu import PLAY_PAUSE, MenuItem, item_from_dict, track_direction

log = logging.getLogger(__name__)

def default_menu(desktop_count: int) -> MenuItem:
    window = MenuItem(
        "Window",
        icon="preferences-system-windows",
        children=[
            MenuItem("Maximize", "window_action", "maximize", "view-fullscreen"),
            MenuItem("Tile right", "window_action", "tile_right", "go-next"),
            MenuItem("Close", "window_action", "close", "window-close"),
            MenuItem("Minimize", "window_action", "minimize", "go-down"),
            MenuItem("Tile left", "window_action", "tile_left", "go-previous"),
        ],
    )
    workspaces = MenuItem(
        "Workspaces",
        icon="preferences-desktop-workspaces",
        children=[MenuItem(f"Workspace {i + 1}", "workspace", i, "") for i in range(desktop_count)],
    )
    root = [
        MenuItem("Terminal", "command", "exo-open --launch TerminalEmulator", "utilities-terminal"),
        MenuItem("Browser", "command", "exo-open --launch WebBrowser", "web-browser"),
        MenuItem("Files", "command", "exo-open --launch FileManager", "system-file-manager"),
        # What this holds depends on the app in use: see holotouch/launcher/appmenu.py.
        MenuItem("This app", "app_actions", icon="keys"),
    ]
    # Music is the fifth of eight, straight down. Entered from the root, the first of these lies
    # to the right, the second straight on down, and the third to the left.
    music = MenuItem(
        "Music",
        icon="applications-multimedia",
        children=[
            MenuItem("Next track", "track", "next", "media-skip-forward"),
            MenuItem("Play / pause", "track", PLAY_PAUSE, "media-playback-start"),
            MenuItem("Previous track", "track", "previous", "media-skip-backward"),
        ],
    )
    root += [music, MenuItem("Windows", "running_windows", icon="view-grid"), window, workspaces]
    return MenuItem("HoloTouch", children=root)


def load_menu(desktop_count: int, path: Path = MENU_PATH) -> MenuItem:
    if not path.exists():
        return default_menu(desktop_count)
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    return MenuItem("HoloTouch", children=[item_from_dict(d) for d in data.get("item", [])])


class Launcher:
    def __init__(self, backend: WindowBackend, root: MenuItem | None = None, browsers: str | None = None):
        """browsers names the web browsers, as [gesture] clap_browsers does, which is what it is if not given."""
        self.backend = backend
        self.root = root or load_menu(backend.desktop_count())
        self.browsers = GestureConfig().clap_browsers if browsers is None else browsers

    def build(self) -> MenuItem:
        """The menu tree with dynamic entries filled in for this moment."""
        root = copy.deepcopy(self.root)
        self._expand(root)
        return root

    def _expand(self, item: MenuItem) -> None:
        if item.type == "running_windows":
            item.children = [
                MenuItem(w.title[:40] or w.wm_class or "Window", "activate_window", w.id, w.wm_class.lower())
                for w in self.backend.windows()
            ]
        elif item.type == "app_actions":
            # The keys go to whatever has the keyboard, so it is that app's they are, not those
            # of the one the hand is over.
            kind = app_kind(self.backend.active_window(), self.browsers)
            item.name, item.children = kind.name, copy.deepcopy(list(kind.items))
        for child in item.children:
            self._expand(child)

    def activate(self, item: MenuItem, target: WindowInfo | None) -> None:
        backend = self.backend
        if item.type == "command":
            self._spawn(str(item.data), shell=True)
        elif item.type == "app":
            self._spawn(["gtk-launch", str(item.data)], shell=False)
        elif item.type == "workspace":
            backend.switch_desktop(int(item.data))
        elif item.type == "activate_window":
            backend.activate(int(item.data))
        elif item.type == "track":
            if item.data == PLAY_PAUSE:
                backend.play_pause()
            else:
                backend.skip_track(track_direction(item))
        elif item.type == "key":
            backend.press_key(str(item.data))
        elif target is None:
            log.info("menu item %r needs a target window", item.name)
        elif item.type == "send_to_workspace":
            backend.set_window_desktop(target.id, int(item.data))
        elif item.type == "window_action":
            self._window_action(str(item.data), target)

    def _window_action(self, action: str, target: WindowInfo) -> None:
        backend = self.backend
        if action == "close":
            backend.close(target.id)
        elif action == "minimize":
            backend.minimize(target.id)
        elif action == "maximize":
            backend.set_maximized(target.id, not target.maximized)
        elif action in ("tile_left", "tile_right"):
            x, y, w, h = backend.workarea()
            if target.maximized:
                backend.set_maximized(target.id, False)
            half = w // 2
            backend.move_resize(target.id, x + (half if action == "tile_right" else 0), y, half, h)
        else:
            log.warning("unknown window action %r", action)

    @staticmethod
    def _spawn(command, shell: bool) -> None:
        try:
            subprocess.Popen(
                command,
                shell=shell,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            log.error("could not launch %r: %s", command, exc)

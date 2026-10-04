"""The camera app the two-handed peace sign opens, and the pressing of its shutter."""

from __future__ import annotations

import logging
import shutil

from holotouch.config import Config
from holotouch.core.actions import WindowBackend

log = logging.getLogger(__name__)

# Tried in this order when [gesture] camera_command names no camera app.
_CAMERA_APPS = ("snapshot", "cheese", "kamoso", "guvcview")
_APPEAR_S = 15.0  # how long the app has to show a window before the photo is given up
_FOCUS_S = 0.3  # how long the window manager is given to hand the app the keyboard
_FOCUS_TRIES = 5


def camera_command(cfg: Config) -> str:
    """The shell command that opens the camera app; empty if none is configured or installed."""
    return cfg.gesture.camera_command or next((app for app in _CAMERA_APPS if shutil.which(app)), "")


class Shutter:
    """Takes a photo in a camera app that has just been started, by pressing its shutter key.

    Camera apps offer no other way in. The app's window is the one that was not there before;
    it is given time to start the camera, and the key is pressed only while that window has the
    keyboard, so it is never typed into anything else.
    """

    def __init__(self, backend: WindowBackend, cfg: Config, now: float):
        """Made just before the app is started."""
        self.backend = backend
        self.cfg = cfg
        self._before = {win.id for win in backend.all_windows()}
        self._started = now
        self._window: int | None = None
        self._due = 0.0
        self._tries = 0

    def step(self, now: float) -> bool:
        """Call every tick; False once the key has been pressed or the photo given up."""
        g = self.cfg.gesture
        if not g.camera_shutter_key:
            return False
        if self._window is None:
            new = [win for win in self.backend.all_windows() if win.id not in self._before]
            if new:
                self._window = new[0].id
                self.backend.activate(self._window)
                self._due = now + g.camera_shutter_ms / 1000.0
            elif now - self._started > _APPEAR_S:
                log.warning("the camera app showed no window; no photo taken")
                return False
            return True
        if now < self._due:
            return True
        if self.backend.get(self._window) is None:
            return False  # closed before the photo
        active = self.backend.active_window()
        if active is None or active.id != self._window:
            self._tries += 1
            if self._tries > _FOCUS_TRIES:
                log.warning("the camera app does not have the keyboard; no photo taken")
                return False
            self.backend.activate(self._window)
            self._due = now + _FOCUS_S
            return True
        log.info("pressing %r in the camera app to take a photo", g.camera_shutter_key)
        self.backend.press_key(g.camera_shutter_key)
        return False

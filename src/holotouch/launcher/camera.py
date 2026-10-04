"""The photo the two-handed peace sign takes.

HoloTouch takes it itself, from the camera it is watching the hands with: the frame in hand when
the sign has been held long enough is saved, which takes no time at all. Where
[gesture] camera_command names a camera app, that is opened instead and its shutter pressed,
which takes as long as the app does to start, and the webcam has to be lent to it meanwhile.
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime
from pathlib import Path

from holotouch.config import Config
from holotouch.core.actions import WindowBackend

log = logging.getLogger(__name__)

_ANSWER_S = 2.0  # how long the camera has to say that the photo is saved
_SHOWN_S = 2.5  # how long the overlay shows the photo that was taken
_FAILED_SHOWN_S = 2.0  # and how long it says that none could be
NO_PHOTO = "No photo taken"
_APPEAR_S = 15.0  # how long the app has to show a window before the photo is given up
_FOCUS_S = 0.3  # how long the window manager is given to hand the app the keyboard
_FOCUS_TRIES = 5


def camera_command(cfg: Config) -> str:
    """The shell command that opens a camera app; empty for HoloTouch to take the photo itself."""
    return cfg.gesture.camera_command.strip()


def photo_dir(cfg: Config) -> Path:
    """Where photos go: [gesture] camera_dir, or HoloTouch in the Pictures folder."""
    if cfg.gesture.camera_dir:
        return Path(cfg.gesture.camera_dir).expanduser()
    try:
        pictures = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True, timeout=2).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pictures = ""
    # With no Pictures folder of its own, xdg-user-dir names the home directory.
    home = Path.home()
    return (Path(pictures) if pictures and Path(pictures) != home else home / "Pictures") / "HoloTouch"


def photo_path(directory: Path, when: datetime) -> Path:
    """The file a photo taken then is saved as: one that is not there yet."""
    name = f"Photo {when:%Y-%m-%d %H-%M-%S}"
    path, n = directory / f"{name}.jpg", 1
    while path.exists():
        n += 1
        path = directory / f"{name} ({n}).jpg"
    return path


class Photographer:
    """Call take() when a photo is wanted, and step() every tick.

    The source is whatever the hands are tracked from: it is asked to save the frame it has next
    (snap), and says how that went (photos).
    """

    def __init__(self, cfg: Config, source):
        self.cfg = cfg
        self.source = source
        self._dir: Path | None = None  # found when the first photo is taken
        self._due: float | None = None  # when the photo asked for is given up
        self._photo, self._photo_until = "", 0.0
        self._failed_until = 0.0

    def take(self, now: float) -> None:
        if self._dir is None:
            self._dir = photo_dir(self.cfg)
        if self.source.snap(photo_path(self._dir, datetime.now())):
            self._due = now + _ANSWER_S
        else:
            self._fail(now, "there is no camera to take it with")

    def step(self, now: float) -> tuple[str, str]:
        """What the overlay should show: the photo just taken, and a note if one could not be. Each "" for nothing."""
        for path, problem in self.source.photos():
            self._due = None
            if path:
                log.info("took a photo: %s", path)
                self._photo, self._photo_until = path, now + _SHOWN_S
            else:
                self._fail(now, problem)
        if self._due is not None and now > self._due:
            self._due = None
            self._fail(now, "the camera did not answer")
        return (self._photo if now < self._photo_until else ""), (NO_PHOTO if now < self._failed_until else "")

    def _fail(self, now: float, why: str) -> None:
        log.warning("no photo was taken: %s", why)
        self._failed_until = now + _FAILED_SHOWN_S


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

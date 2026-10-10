"""The volume, the screen's brightness and the music: the same on every desktop, so every real backend has these."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class SystemControls:
    """A backend's dials and music keys. The backend calls _apply_volume() from its poll()."""

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

    def skip_track(self, direction: int) -> None:
        self._playerctl("next" if direction > 0 else "previous")

    def play_pause(self) -> None:
        self._playerctl("play-pause")

    def _playerctl(self, command: str) -> None:
        # playerctl finds the player last in use. Like the volume, it is not waited for.
        try:
            self._track_call = subprocess.Popen(["playerctl", command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            log.warning("cannot tell the music to %s: playerctl is needed (%s)", command, exc.strerror or exc)

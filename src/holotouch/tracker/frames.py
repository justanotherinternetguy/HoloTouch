"""Saves the camera's frames beside a recording, so a slower, better model can label them later,
and one frame as a photo when the core asks for it.

Imported only in the tracker process (it pulls in OpenCV).
"""

from __future__ import annotations

import logging
import queue
import threading
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)

_QUALITY = 90
_PHOTO_QUALITY = 95
_BACKLOG = 64  # frames that may wait to be written; beyond this new ones are dropped


def frame_name(captured_at: float) -> str:
    """The file a frame is saved under: its capture time in microseconds.

    A recording's t_capture gives the same name, which is how landmarks are matched to pictures.
    """
    return f"{round(captured_at * 1e6):015d}.jpg"


def save_photo(rgb: np.ndarray, path: Path, mirrored: bool) -> None:
    """Save a frame as a photo: as the camera saw it, not as the mirror the tracker is shown."""
    picture = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    if mirrored:
        picture = cv2.flip(picture, 1)
    ok, data = cv2.imencode(".jpg", picture, [cv2.IMWRITE_JPEG_QUALITY, _PHOTO_QUALITY])
    if not ok:
        raise OSError("JPEG encoding failed")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Written under another name first, so a file that exists is always a whole picture.
    partial = path.with_suffix(".part")
    partial.write_bytes(data)
    partial.replace(path)


class FrameWriter:
    """Writes frames as JPEGs on its own thread, so encoding never holds up the camera."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.dropped = 0
        directory.mkdir(parents=True, exist_ok=True)
        self._queue: queue.Queue = queue.Queue(maxsize=_BACKLOG)
        self._thread = threading.Thread(target=self._run, name="frame-writer", daemon=True)
        self._thread.start()

    def save(self, rgb: np.ndarray, captured_at: float) -> None:
        """Queue a frame exactly as the landmarker sees it (mirrored RGB)."""
        try:
            self._queue.put_nowait((rgb, captured_at))
        except queue.Full:
            self.dropped += 1

    def _run(self) -> None:
        while (item := self._queue.get()) is not None:
            rgb, captured_at = item
            path = self.directory / frame_name(captured_at)
            try:
                ok, data = cv2.imencode(".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, _QUALITY])
                if not ok:
                    raise OSError("JPEG encoding failed")
                # Written under another name first, so a file that exists is always a whole picture.
                partial = path.with_suffix(".part")
                partial.write_bytes(data)
                partial.replace(path)
            except OSError as exc:
                if not self.dropped:
                    log.error("cannot save camera frames in %s: %s", self.directory, exc)
                self.dropped += 1

    def close(self) -> None:
        """Write out what is still waiting, then stop."""
        self._queue.put(None)
        self._thread.join()
        if self.dropped:
            log.warning("%d camera frames were not saved", self.dropped)

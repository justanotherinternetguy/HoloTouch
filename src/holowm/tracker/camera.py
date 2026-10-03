"""Webcam capture through V4L2. Imported only in the tracker process (it pulls in OpenCV)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import time

import cv2
import numpy as np

from holowm.config import CameraConfig

log = logging.getLogger(__name__)


def apply_camera_controls(cfg: CameraConfig) -> None:
    """Stop the camera halving its frame rate in dim light, and match the mains frequency."""
    if not cfg.fix_controls or shutil.which("v4l2-ctl") is None:
        return
    controls = {
        "exposure_dynamic_framerate": 0,
        "power_line_frequency": 2 if cfg.power_line_hz == 60 else 1,
    }
    for name, value in controls.items():
        result = subprocess.run(
            ["v4l2-ctl", "-d", cfg.device, "-c", f"{name}={value}"], capture_output=True, text=True
        )
        if result.returncode != 0:
            log.debug("camera control %s not applied: %s", name, result.stderr.strip())


class Camera:
    def __init__(self, cfg: CameraConfig):
        self.cfg = cfg
        apply_camera_controls(cfg)
        self._capture = cv2.VideoCapture(cfg.device, cv2.CAP_V4L2)
        if not self._capture.isOpened():
            raise RuntimeError(f"cannot open camera {cfg.device}")
        self._capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)
        self._capture.set(cv2.CAP_PROP_FPS, cfg.fps)
        self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def read(self) -> tuple[np.ndarray, float] | None:
        """The next frame as mirrored RGB, with the time it was grabbed (before decoding)."""
        if not self._capture.grab():
            return None
        grabbed_at = time.monotonic()
        ok, frame = self._capture.retrieve()
        if not ok:
            return None
        if self.cfg.mirror:
            frame = cv2.flip(frame, 1)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), grabbed_at

    def close(self) -> None:
        self._capture.release()

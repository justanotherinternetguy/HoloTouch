"""MediaPipe hand and face landmarkers in live-stream mode. Imported only in the tracker process."""

from __future__ import annotations

import logging
import threading
import time
import urllib.request
from pathlib import Path
from typing import Callable

import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    HandLandmarker,
    HandLandmarkerOptions,
    RunningMode,
)

from holowm.config import CACHE_DIR, TrackerConfig
from holowm.tracker.types import FaceSample, FrameSample, HandSample

log = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/"
    "hand_landmarker.task"
)
MODEL_PATH = CACHE_DIR / "hand_landmarker.task"
FACE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/"
    "face_landmarker.task"
)
FACE_MODEL_PATH = CACHE_DIR / "face_landmarker.task"


def ensure_model(path: Path = MODEL_PATH, url: str = MODEL_URL) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        log.info("downloading %s", path)
        partial = path.with_suffix(".part")
        urllib.request.urlretrieve(url, partial)
        partial.rename(path)
    return path


def _points(landmarks) -> np.ndarray:
    return np.array([[p.x, p.y, p.z] for p in landmarks], dtype=np.float32)


class Landmarker:
    """Submit frames with their capture time; on_sample is called from MediaPipe's thread."""

    def __init__(self, cfg: TrackerConfig, on_sample: Callable[[FrameSample], None]):
        self._on_sample = on_sample
        self._captured: dict[int, float] = {}
        self._lock = threading.Lock()
        self._last_ms = 0
        self._seq = 0
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(ensure_model())),
            running_mode=RunningMode.LIVE_STREAM,
            num_hands=cfg.num_hands,
            min_hand_detection_confidence=cfg.detection_confidence,
            min_hand_presence_confidence=cfg.presence_confidence,
            min_tracking_confidence=cfg.tracking_confidence,
            result_callback=self._on_result,
        )
        self._landmarker = HandLandmarker.create_from_options(options)
        self._face: FaceSample | None = None  # the newest face, until it is sent with a frame
        self._faces = self._face_landmarker() if cfg.face else None

    def _face_landmarker(self) -> FaceLandmarker | None:
        # The face is only needed for gestures that touch it, so tracking carries on without it.
        try:
            options = FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(ensure_model(FACE_MODEL_PATH, FACE_MODEL_URL))),
                running_mode=RunningMode.LIVE_STREAM,
                num_faces=1,
                result_callback=self._on_face,
            )
            return FaceLandmarker.create_from_options(options)
        except Exception as exc:
            log.warning("face tracking is off: %s: %s", type(exc).__name__, exc)
            return None

    def submit(self, rgb: np.ndarray, captured_at: float, face: bool = False) -> None:
        """Look for hands in the frame, and for the face too if asked."""
        with self._lock:
            # MediaPipe requires strictly increasing millisecond timestamps.
            stamp = max(int(captured_at * 1000), self._last_ms + 1)
            self._last_ms = stamp
            self._captured[stamp] = captured_at
            # Frames MediaPipe drops under load never reach the callback; forget them.
            for old in [s for s in self._captured if s < stamp - 2000]:
                del self._captured[old]
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        if face and self._faces is not None:
            self._faces.detect_async(image, stamp)
        self._landmarker.detect_async(image, stamp)

    def _on_face(self, result, image, stamp: int) -> None:
        if result.face_landmarks:
            sample = FaceSample(_points(result.face_landmarks[0]))
            with self._lock:
                self._face = sample

    def _on_result(self, result, image, stamp: int) -> None:
        with self._lock:
            captured_at = self._captured.pop(stamp, None)
            self._seq += 1
            seq = self._seq
            if captured_at is not None:
                face, self._face = self._face, None
        if captured_at is None:
            return
        hands = [
            HandSample(
                handedness=result.handedness[i][0].category_name,
                score=float(result.handedness[i][0].score),
                image=_points(result.hand_landmarks[i]),
                world=_points(result.hand_world_landmarks[i]),
            )
            for i in range(len(result.hand_landmarks))
        ]
        self._on_sample(FrameSample(seq, captured_at, time.monotonic(), hands, face))

    def close(self) -> None:
        self._landmarker.close()
        if self._faces is not None:
            self._faces.close()

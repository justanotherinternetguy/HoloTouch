"""The user's face as the camera sees it, and where a hand is relative to it."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from holowm.config import Config
from holowm.core.filters import OneEuro
from holowm.tracker.types import FACE_CHEEKS, FACE_CHIN, FACE_FOREHEAD, FACE_OVAL, FaceSample

if TYPE_CHECKING:
    from holowm.core.hands import Hand

# Size of MediaPipe's reference face in metres: forehead to chin, and cheek to cheek. Set against
# the size of the face in the picture, it gives the scale of the picture at the face.
_HEIGHT_M = 0.177
_WIDTH_M = 0.153
# A hand on the chin can hide the face from the tracker; it is taken to stay put for this long.
_LOST_S = 1.5
# 1€ filter on the points used, in frame heights. A head moves slowly, and its estimated position
# jumps about when a hand covers part of it.
_MIN_CUTOFF, _BETA = 1.0, 4.0
_KEY = [FACE_CHIN, FACE_FOREHEAD, *FACE_CHEEKS]


class FaceTrack:
    def __init__(self, cfg: Config):
        self._aspect = cfg.camera.width / cfg.camera.height
        self._filter = OneEuro(_MIN_CUTOFF, _BETA)
        self._seen = float("-inf")
        self.chin = np.zeros(2)  # in frame heights, like Hand.frame_points
        self.size = 0.0  # forehead to chin in frame heights, had the face been square to the camera
        self.scale = 0.0  # frame heights per metre at the face
        self.outline = np.zeros((0, 2))  # for the debug view, in fractions of the frame

    def update(self, face: FaceSample, t: float) -> None:
        if t - self._seen > _LOST_S:
            self._filter.reset()
        chin, forehead, cheek, other_cheek = self._filter(face.image[_KEY, :2] * (self._aspect, 1.0), t)
        height = float(np.linalg.norm(forehead - chin))
        width = float(np.linalg.norm(cheek - other_cheek))
        # Nodding shortens the height and turning shortens the width, so the larger is the truer.
        self.scale = max(height / _HEIGHT_M, width / _WIDTH_M)
        self.size = self.scale * _HEIGHT_M
        self.chin = chin
        self.outline = face.image[list(FACE_OVAL), :2]
        self._seen = t

    def visible(self, now: float) -> bool:
        return now - self._seen <= _LOST_S and self.size > 0.0

    def reach(self, hand: "Hand") -> float:
        """How far the nearest part of the hand is from the chin in the picture, in face heights."""
        return float(np.linalg.norm(hand.frame_points - self.chin, axis=1).min()) / self.size

    def closeness(self, hand: "Hand") -> float:
        """How much nearer the camera the hand is than the face: 1 level with it, 2 at half the distance."""
        return hand.image_scale / self.scale

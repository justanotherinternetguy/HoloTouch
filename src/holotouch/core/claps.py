"""Claps, as the camera sees them: the two palms apart, and then together a moment later.

Nothing is heard. Hands that meet are read badly, as one hand or as none, so the palms count as
having met when they vanish on their way together, too.
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np

from holotouch.config import GestureConfig
from holotouch.core.hands import Hand
from holotouch.tracker.types import INDEX_MCP, PINKY_MCP, WRIST

_MERGE_S = 0.12  # hands not seen for this long after closing in on each other have met
_SHORTEST_S = 0.1  # two meetings nearer in time than this are one clap read twice


def palm_gap(a: Hand, b: Hand) -> float:
    """Metres between two palms, as near as the picture tells: it does not show which is in front."""
    centres = [hand.frame_points[[WRIST, INDEX_MCP, PINKY_MCP]].mean(axis=0) for hand in (a, b)]
    scale = (a.image_scale + b.image_scale) / 2.0  # frame heights per metre
    return float(np.linalg.norm(centres[0] - centres[1])) / max(scale, 1e-6)


class Claps:
    """Call update() with the hands after every camera frame; take() is True once for each two claps."""

    def __init__(self, cfg: GestureConfig):
        self.cfg = cfg
        self.reset()

    def reset(self) -> None:
        self._apart_at = -math.inf  # when the palms were last seen apart
        self._gap: float | None = None  # how far apart they were when both were last seen, and when
        self._gap_at = -math.inf
        self._met = True  # they have met, and not parted since
        self.met_at = -math.inf  # when they were last together, clapping or not
        self._claps: deque[float] = deque()
        self._doubled = False

    def update(self, hands: list[Hand], t: float) -> None:
        g = self.cfg
        seen = [hand for hand in hands if hand.last_seen == t]
        if len(seen) == 2:
            gap = palm_gap(*seen)
            if gap >= g.clap_apart:
                self._apart_at, self._met = t, False
            elif gap <= g.clap_together:
                self._meet(t)
            self._gap, self._gap_at = gap, t
        elif self._gap is not None and self._gap < g.clap_apart and t - self._gap_at <= _MERGE_S:
            self._meet(t)

    def _meet(self, t: float) -> None:
        g = self.cfg
        self.met_at = t
        # Hands brought together slowly are not clapping.
        if self._met or (t - self._apart_at) * 1000.0 > g.clap_close_ms:
            return
        self._met = True
        while self._claps and (t - self._claps[0]) * 1000.0 > g.clap_window_ms:
            self._claps.popleft()
        if self._claps and t - self._claps[-1] < _SHORTEST_S:
            return
        self._claps.append(t)
        if len(self._claps) >= 2:
            self._claps.clear()
            self._doubled = True

    def take(self) -> bool:
        doubled, self._doubled = self._doubled, False
        return doubled

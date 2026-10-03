"""Turn a knob: make a claw, as if gripping one, and rotate the hand in place.

The right hand's knob is the sound volume and the left hand's the screen brightness. How far
the hand has turned from where it first settled sets how far the level has moved from where it
was; opening or closing the hand lets go of the knob.
"""

from __future__ import annotations

import math
from collections import deque

from holowm.core.filters import OneEuro
from holowm.core.hands import Hand
from holowm.core.interactions.base import Interaction
from holowm.core.overlay_state import OverlayState
from holowm.core.poses import Pose
from holowm.tracker.types import INDEX_MCP, PINKY_MCP

_SETTLE_S = 0.25  # the way the hand is turned after this long is where the knob starts
_UNSURE_S = 0.3  # how long the pose may be unclear before the knob is let go of
_APPLY_S = 0.05  # the level is set at most this often
# Letting go turns the hand a little before the pose is seen to change, so the level is put back
# to where it stood this long before.
_RELEASE_S = 0.25
_LOWEST = {"brightness": 0.05}  # a screen turned right down could not be seen to turn it back up


def _roll(hand: Hand) -> float:
    """How the hand is turned in the picture, in degrees: the line of the knuckles, index to pinky."""
    across = hand.frame_points[PINKY_MCP] - hand.frame_points[INDEX_MCP]
    return math.degrees(math.atan2(across[1], across[0]))


class KnobInteraction(Interaction):
    def __init__(self, engine, hand: Hand, now: float, dial: str):
        """dial is what the knob turns: "volume" or "brightness"."""
        super().__init__(engine)
        self.hand_id = hand.id
        self.hand_ids = (hand.id,)
        self.dial = dial
        self.level = self.backend.dial(dial)  # 0..1; None when it cannot be read
        self._from = self.level
        self._started = self._seen = now
        self._applied = 0.0
        f = self.cfg.filter
        self._smooth = OneEuro(f.tilt_min_cutoff, f.tilt_beta, f.d_cutoff)
        self._raw = _roll(hand)
        self._turn = 0.0  # degrees turned since the gesture began, clockwise positive, followed all the way round
        self._rest: float | None = None  # the turn at which the level is where it started
        self._history: deque[tuple[float, float]] = deque()  # (time, level) over the last _RELEASE_S

    def update(self, now: float) -> bool:
        hand = self.engine.tracker.get(self.hand_id)
        if self.level is None:
            return False
        if hand is None or hand.pose is not Pose.CLAW:
            # A claw is easy to misread for a moment; anything that lasts has let go of the knob.
            if hand is not None and hand.pose is Pose.NEUTRAL and now - self._seen <= _UNSURE_S:
                return True
            if hand is not None:
                hand.consumed = True
            self._let_go()
            return False
        self._seen = now
        self._history.append((now, self.level))
        while self._history[0][0] < now - _RELEASE_S:
            self._history.popleft()
        raw = _roll(hand)
        self._turn += (raw - self._raw + 180.0) % 360.0 - 180.0
        self._raw = raw
        turn = float(self._smooth(self._turn, hand.last_seen))
        if self._rest is None:
            if now - self._started < _SETTLE_S:
                return True
            self._rest = turn
        g = self.cfg.gesture
        lean = turn - self._rest
        moved = math.copysign(max(abs(lean) - g.knob_dead_deg, 0.0), lean) / g.knob_full_deg
        level = min(max(self._from + (-moved if g.knob_invert else moved), _LOWEST.get(self.dial, 0.0)), 1.0)
        if abs(level - self.level) >= 0.01 and now - self._applied >= _APPLY_S:
            self.level, self._applied = level, now
            self.backend.set_dial(self.dial, level)
        return True

    def _let_go(self) -> None:
        if self._history and abs(self._history[0][1] - self.level) >= 0.01:
            self.level = self._history[0][1]
            self.backend.set_dial(self.dial, self.level)

    def cancel(self) -> None:
        pass  # the level stays where it was turned to

    def decorate(self, overlay: OverlayState) -> None:
        hand = self.engine.tracker.get(self.hand_id)
        if hand is not None and self.level is not None:
            overlay.knob, overlay.knob_x, overlay.knob_y = self.level, hand.x, hand.y
            overlay.knob_name = self.dial.capitalize()

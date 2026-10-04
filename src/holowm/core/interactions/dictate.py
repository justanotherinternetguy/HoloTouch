"""Dictate: the letter Y of the manual alphabet, held up, records the microphone until it is dropped.

The engine only says that dictation is wanted (Engine.dictating). Whoever runs the engine does
the recording, and types what was said into whatever has the keyboard once the sign is let go.
"""

from __future__ import annotations

from holowm.core.hands import Hand
from holowm.core.interactions.base import Interaction
from holowm.core.overlay_state import OverlayState
from holowm.core.poses import Pose

_UNSURE_S = 0.3  # how long the hand's pose may be unclear before the sign is taken to be dropped


class DictateInteraction(Interaction):
    def __init__(self, engine, hand: Hand, now: float):
        super().__init__(engine)
        self.hand_id = hand.id
        self.hand_ids = (hand.id,)
        self.started = self._seen = now

    def update(self, now: float) -> bool:
        hand = self.engine.tracker.get(self.hand_id)
        if hand is None:
            return False
        if now - self.started >= self.cfg.gesture.dictate_max_s:
            hand.consumed = True  # the sign has to be made afresh to go on
            return False
        if hand.pose is Pose.Y_SIGN:
            self._seen = now
        elif hand.pose is Pose.OPEN or now - self._seen > _UNSURE_S:
            return False
        return True

    def decorate(self, overlay: OverlayState) -> None:
        overlay.dictation = "listening"

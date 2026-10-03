"""Open the camera app: both hands hold up two fingers, the peace sign, until the ring completes.

One hand held that way scrolls, and nothing in the hand tells the two apart, which is why it
takes both.
"""

from __future__ import annotations

from holowm.core.hands import Hand
from holowm.core.interactions.base import Interaction
from holowm.core.overlay_state import OverlayState
from holowm.core.poses import Pose

_UNSURE_S = 0.3  # how long a hand's pose may be unclear before the sign is taken to be dropped


class CameraInteraction(Interaction):
    def __init__(self, engine, hands: list[Hand], now: float):
        super().__init__(engine)
        self.hand_ids = tuple(hand.id for hand in hands)
        self.started = self._seen = now
        self.progress = 0.0

    def update(self, now: float) -> bool:
        hands = [self.engine.tracker.get(hand_id) for hand_id in self.hand_ids]
        if any(hand is None for hand in hands):
            return False
        if all(hand.pose is Pose.TWO_FINGER for hand in hands):
            self._seen = now
        elif any(hand.pose is Pose.OPEN for hand in hands) or now - self._seen > _UNSURE_S:
            return self._end(hands)
        self.progress = (now - self.started) * 1000.0 / self.cfg.gesture.camera_hold_ms
        if self.progress >= 1.0:
            self.engine.camera_wanted = True
            return self._end(hands)
        return True

    @staticmethod
    def _end(hands: list[Hand]) -> bool:
        # A hand still holding up two fingers does not go on to scroll; it has to make them afresh.
        for hand in hands:
            hand.consumed = True
        return False

    def decorate(self, overlay: OverlayState) -> None:
        hands = [self.engine.tracker.get(hand_id) for hand_id in self.hand_ids]
        if any(hand is None for hand in hands):
            return
        overlay.hold_progress = min(self.progress, 1.0)
        overlay.hold_x = sum(hand.x for hand in hands) / len(hands)
        overlay.hold_y = sum(hand.y for hand in hands) / len(hands)
        overlay.hold_name = "Camera"

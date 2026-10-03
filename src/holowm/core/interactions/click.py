"""The left mouse button: down while thumb and middle finger are pinched, up when they part.

A quick pinch is a click, two are a double click, and a pinch that is carried somewhere drags.
"""

from __future__ import annotations

import logging

from holowm.core.hands import Hand
from holowm.core.interactions.base import Interaction
from holowm.core.poses import Pose

log = logging.getLogger(__name__)


class ClickInteraction(Interaction):
    def __init__(self, engine, hand: Hand, now: float):
        super().__init__(engine)
        self.hand_id = hand.id
        self.hand_ids = (hand.id,)
        self.origin = (hand.x, hand.y)
        # A held hand wanders by a few dozen pixels, and far less than that makes a click into a
        # drag. So the pointer stays where the button went down until the hand has clearly set off.
        self._dragging = False
        self._at = engine.click_point(hand, now)
        log.debug("mouse button down at %d, %d", *self._at)
        self.backend.button_down(round(self._at[0]), round(self._at[1]))

    def update(self, now: float) -> bool:
        hand = self.engine.tracker.get(self.hand_id)
        if hand is None or hand.pose is not Pose.PINCH_MIDDLE:
            self.backend.button_up()
            return False
        if not self._dragging:
            slop = self.engine.click_slop
            self._dragging = (hand.x - self.origin[0]) ** 2 + (hand.y - self.origin[1]) ** 2 > slop * slop
            if self._dragging:
                log.debug("the hand has set off: dragging")
        if self._dragging and (hand.x, hand.y) != self._at:
            self._at = (hand.x, hand.y)
            self.backend.pointer_to(round(hand.x), round(hand.y))
        return True

    def cancel(self) -> None:
        self.backend.button_up()

"""Scroll the window under the hand by tilting the extended index and middle fingers.

The hand stays where it is. How far the fingers lean from where they first settled sets the
speed, so holding a tilt keeps scrolling; opening the hand stops it.

Tipped far enough down, the two fingers lie over the rest of the hand in the picture and the
hand can no longer be read: it comes out as neutral, as a pinch, even as a fist. The tilt still
reads steep, so while it does, and the index finger is not curled right up, the gesture carries
on whatever the pose is read as.
"""

from __future__ import annotations

import math

from holowm.core.filters import OneEuro
from holowm.core.hands import Hand
from holowm.core.interactions.base import Interaction
from holowm.core.overlay_state import OverlayState
from holowm.core.poses import Pose

# The tilt the fingers have come to rest at after this long counts as "not scrolling". The reading
# keeps rising for about 0.3 s after the pose is first made, by some 25 degrees from an open hand.
_SETTLE_S = 0.35
_UNSURE_S = 0.3  # how long the pose may be unclear before the gesture is taken to be over
_STEEP_DEG = 90.0  # fingers pointing at the camera or lower: from here on only the tilt is believed
# A real fist also reads as a steep tilt, but with the index finger curled right up (0.3 to 0.55,
# against 0.7 and more for fingers tipped down), and that ends the gesture as it should.
_STEEP_STRAIGHT = 0.6


def _from_upright(degrees: float) -> float:
    """A tilt as -90 to 270 degrees, so that it runs on smoothly through pointing straight down.

    Fingers cannot lean further back than flat, which makes that the place to cut the circle.
    """
    return (degrees + 90.0) % 360.0 - 90.0


class ScrollInteraction(Interaction):
    def __init__(self, engine, hand: Hand, now: float):
        super().__init__(engine)
        self.hand_id = hand.id
        self.hand_ids = (hand.id,)
        self.rate = 0.0  # -1..1 of the top speed; positive scrolls down
        self._started = self._last = self._seen = now
        # Steady while a tilt is held, quick to follow when it changes.
        f = self.cfg.filter
        self._smooth = OneEuro(f.tilt_min_cutoff, f.tilt_beta, f.d_cutoff)
        self._tilt = float(self._smooth(_from_upright(hand.features.finger_tilt), hand.last_seen))
        self._rest: float | None = None  # the tilt that means no scrolling
        # Wheel events are delivered to the pointer position, so park the pointer under the hand
        # for the duration of the gesture and put it back afterwards.
        self._saved_pointer = self.backend.pointer_pos()
        self.backend.warp_pointer(round(hand.x), round(hand.y))

    def update(self, now: float) -> bool:
        hand = self.engine.tracker.get(self.hand_id)
        dt, self._last = now - self._last, now
        if hand is None:
            self.cancel()
            return False
        # Filtered once per camera sample (a repeated time is ignored).
        self._tilt = float(self._smooth(_from_upright(hand.features.finger_tilt), hand.last_seen))
        steep = self._rest is not None and self._tilt >= _STEEP_DEG and hand.features.straight[0] >= _STEEP_STRAIGHT
        if hand.pose is Pose.TWO_FINGER or steep:
            self._seen = now
        elif hand.pose is not Pose.OPEN and now - self._seen <= _UNSURE_S:
            # Tilted fingers are easy to misread for a moment: pause, but keep the resting tilt.
            self.rate = 0.0
            return True
        else:
            # A pinch or a fist read as the scroll ends is as doubtful as the poses read during
            # it, so it starts nothing; it has to be made afresh.
            hand.consumed = True
            self.cancel()
            return False
        if self._rest is None:
            if now - self._started < _SETTLE_S:
                return True
            self._rest = self._tilt
        g = self.cfg.gesture
        lean = self._tilt - self._rest
        span = max(g.scroll_full_deg - g.scroll_dead_deg, 1e-6)
        self.rate = math.copysign(min(max((abs(lean) - g.scroll_dead_deg) / span, 0.0), 1.0), lean)
        # Fingers tipping forward and down scroll down, which is a negative wheel movement.
        notches = -self.rate * g.scroll_speed * dt * (-1.0 if g.scroll_invert else 1.0)
        if notches:
            self.backend.scroll(notches)
        return True

    def cancel(self) -> None:
        self.backend.warp_pointer(*self._saved_pointer)

    def decorate(self, overlay: OverlayState) -> None:
        overlay.scrolling = True
        for view in overlay.hands:
            if view.id == self.hand_id:
                view.scroll = self.rate

"""Scroll the window under the hand by tilting the extended index and middle fingers.

The hand stays where it is, and holding a tilt keeps scrolling; opening the hand stops it.

The two ways are not alike, because the fingers do not have the same room each way. Held up,
they come to rest leaning toward the camera, anywhere up to 60 degrees, and get there a second or
more after the pose is made. Tipped down they point at the camera or below it, which reads as
70 to 190 degrees. Leaned back they can only straighten up, which reads as 20 to 28 degrees, and
no lower however far back the hand goes. So:

- Tipped further toward the camera than a resting hand ever leans, they scroll down, the faster
  the further. A lean short of that scrolls nothing, and where it is held is where they rest now.
- Leaned back from where they rest, they scroll up, and reach the top speed sooner.

Tipped toward the camera, the two fingers no longer read as extended, and tipped far enough down
they lie over the rest of the hand in the picture: the hand comes out as neutral, as a pinch,
even as a fist. So once the gesture has begun it also carries on while the two fingers stand out
from the ring finger and the pinky, or while the tilt reads steep and the index finger is not
curled right up.
"""

from __future__ import annotations

import math
from collections import deque

from holotouch.core.filters import OneEuro
from holotouch.core.hands import Hand
from holotouch.core.interactions.base import Interaction
from holotouch.core.overlay_state import OverlayState
from holotouch.core.poses import Pose

# The tilt the fingers come to rest at counts as "not scrolling". The reading keeps rising for
# about 0.3 s after the pose is first made, by some 25 degrees from an open hand, and a hand still
# on its way into place goes on tilting for a second or more. So it is taken once the fingers are
# still, and no sooner than _SETTLE_S after the pose. They are still when the tilt read over the
# last _STILL_S is, on average, within _STILL_DEG of the tilt read over the _STILL_S before that.
_SETTLE_S = 0.35
_STILL_S = 0.125
_STILL_DEG = 3.0
# Fingers held up sag, by several degrees a second. While they are still and within the dead
# zone, the resting tilt follows them.
_RECENTRE_S = 0.5
# Fingers held up also relax toward the camera, by 20 or 30 degrees over a second or two. Where
# they are held short of scrolling down, the resting tilt follows them, more slowly than it does
# a sag: a lean the hand only passes through should not move it.
_RELAX_S = 0.8
# Scrolling down speeds up over at least this much tilt, however near the fingers rest to where it begins.
_SHORTEST_RAMP_DEG = 20.0
# Fingers straighten up for a moment before they are flicked down, and on the way to an open
# hand. Leaned back, they scroll up only once they have stayed there this long.
_BACK_HOLD_S = 0.3
_UNSURE_S = 0.3  # how long the hand may be unclear before the gesture is taken to be over
# Tipped 50 to 80 degrees and held there, the index and middle fingers read too bent to count as
# extended, but are still this much straighter than the ring finger and the pinky: 0.17 and more.
# In a hand opening, one pointing, a pinch or a fist they are not.
_STAND_OUT = 0.15
_STEEP_DEG = 80.0  # fingers pointing nearly at the camera or lower: from here on only the tilt is believed
# A real fist also reads as a steep tilt, but with the index finger curled right up (0.3 to 0.55,
# against 0.65 and more for fingers tipped down), and that ends the gesture as it should.
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
        self._recent: deque[tuple[float, float]] = deque()  # the tilt as read over the last two _STILL_S
        self._tilt = self._read(hand)
        self._rest: float | None = None  # the tilt that means no scrolling
        self._tipped = False  # tipped forward to scroll down, and not yet back at rest
        self._back_since: float | None = None  # when the fingers leaned back past the dead zone
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
        if hand.last_seen > self._recent[-1][0]:  # once per camera sample
            self._tilt = self._read(hand)
        straight = hand.features.straight
        steep = self._rest is not None and self._tilt >= _STEEP_DEG and straight[0] >= _STEEP_STRAIGHT
        if hand.pose is Pose.TWO_FINGER or steep or min(straight[:2]) - max(straight[2:]) >= _STAND_OUT:
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
        still = self._still()
        if self._rest is None:
            # Fingers pointing at the camera are a tilt already made, not where they rest.
            if now - self._started < _SETTLE_S or not still or self._tilt >= _STEEP_DEG:
                return True
            self._rest = self._tilt
        g = self.cfg.gesture
        dead = g.scroll_dead_deg
        lean = self._tilt - self._rest
        # Coming back up from a tilt the fingers pass their resting place, by up to 14 degrees,
        # and a hand opening reads as fingers leaning right back. So past it nothing scrolls until
        # they are still, and if that is within twice the dead zone, there is where they rest now.
        back = self._tipped and lean < 0.0
        down_from = max(self._rest + dead, g.scroll_down_from_deg)
        if still and self._tilt < down_from and lean > -(2.0 if back else 1.0) * dead:
            follow = _RECENTRE_S if lean < dead else _RELAX_S
            self._rest += lean * (1.0 - math.exp(-dt / follow))
            lean = self._tilt - self._rest
            down_from = max(self._rest + dead, g.scroll_down_from_deg)
            if abs(lean) < dead:
                self._tipped = False
        if lean > -dead:
            self._back_since = None
        elif self._back_since is None:
            self._back_since = now
        if self._tilt >= down_from:
            full_at = max(self._rest + g.scroll_full_deg, down_from + _SHORTEST_RAMP_DEG)
            self.rate = min((self._tilt - down_from) / (full_at - down_from), 1.0)
        elif self._back_since is not None and now - self._back_since >= _BACK_HOLD_S:
            self.rate = -min((-lean - dead) / max(g.scroll_up_full_deg - dead, 1e-6), 1.0)
        else:
            self.rate = 0.0
        if back and (not still or abs(lean) < 2.0 * dead):
            self.rate = 0.0
        # A hand that is opening reads as fingers leaning back, before it reads as open.
        if self.rate < 0.0 and max(straight[2:]) > self.cfg.pose.extend_exit:
            self.rate = 0.0
        if self.rate:
            self._tipped = self.rate > 0.0
        # Fingers tipping forward and down scroll down, which is a negative wheel movement.
        notches = -self.rate * g.scroll_speed * dt * (-1.0 if g.scroll_invert else 1.0)
        if notches:
            self.backend.scroll(notches)
        return True

    def _read(self, hand: Hand) -> float:
        """The tilt of this camera sample, smoothed."""
        t, tilt = hand.last_seen, _from_upright(hand.features.finger_tilt)
        self._recent.append((t, tilt))
        while t - self._recent[0][0] > 2.0 * _STILL_S:
            self._recent.popleft()
        return float(self._smooth(tilt, t))

    def _still(self) -> bool:
        split = self._recent[-1][0] - _STILL_S
        before = [tilt for t, tilt in self._recent if t <= split]
        after = [tilt for t, tilt in self._recent if t > split]
        return bool(before and after) and abs(sum(after) / len(after) - sum(before) / len(before)) <= _STILL_DEG

    def cancel(self) -> None:
        self.backend.warp_pointer(*self._saved_pointer)

    def decorate(self, overlay: OverlayState) -> None:
        overlay.scrolling = True
        for view in overlay.hands:
            if view.id == self.hand_id:
                view.scroll = self.rate

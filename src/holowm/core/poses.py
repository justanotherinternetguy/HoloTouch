"""Hand features and pose classification with hysteresis and time-based debounce."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np

from holowm.config import PoseConfig
from holowm.tracker.types import (
    FINGERS,
    INDEX_MCP,
    INDEX_TIP,
    MIDDLE_MCP,
    MIDDLE_TIP,
    PINKY_MCP,
    PINKY_TIP,
    RING_TIP,
    THUMB_TIP,
    WRIST,
    HandSample,
)


class Pose(Enum):
    NEUTRAL = "neutral"
    OPEN = "open"
    PINCH_INDEX = "pinch_index"
    PINCH_MIDDLE = "pinch_middle"
    PINCH_PINKY = "pinch_pinky"
    FIST = "fist"
    TWO_FINGER = "two_finger"
    CLAW = "claw"


PINCHES = (Pose.PINCH_INDEX, Pose.PINCH_MIDDLE, Pose.PINCH_PINKY)


@dataclass(slots=True)
class HandFeatures:
    palm: np.ndarray  # (2,) palm centre in mirrored-frame coordinates
    pinch_index: float  # thumb tip to index tip in palm lengths: the smaller of two ways of measuring it
    pinch_pinky: float
    pinch_middle: float
    pinch_others: float  # the middle or ring fingertip, whichever is nearer the thumb
    curl: tuple[float, ...]  # fingertip-to-knuckle distance over palm length, index..pinky
    straight: tuple[float, ...]  # 1.0 = fully straight finger, index..pinky
    facing: float  # 1.0 when the palm plane is parallel to the image plane
    # Degrees the index and middle fingers lean from straight up toward the camera: 90 is pointing
    # at the camera, more is pointing down, negative is leaning back.
    finger_tilt: float


# A pinch of thumb and middle finger measures 0.15 to 0.26 between their tips, which is nearer the
# limit for a pinch than is safe, so it is given a wider one. What else it has to satisfy keeps
# that from letting much in: above all that the ring finger and the pinky stand clear, this
# straight or more. They are at 0.96 in a real one. Pointing with one finger also rests the thumb
# on the middle finger, but folds those two away, to about 0.5.
_MIDDLE_PINCH_ENTER = 0.3
_MIDDLE_PINCH_CLEAR = 0.85
_CLAW_REACH = 0.36  # in a claw each fingertip is at least this far from its knuckle; a fist's are nearer
_CLAW_STILL_BENT = 0.89

# How far apart in depth the thumb and index tips may be, by the picture's own estimate, and still
# be taken for touching where they meet in the picture. One pointing at the camera is well past it.
_MAX_DEPTH_GAP = 0.45


def _picture_pinch(image: np.ndarray, aspect: float) -> float:
    """Thumb tip to index fingertip as the picture shows them, in palm lengths.

    The metric landmarks put touching fingertips a third of a palm apart when the palm faces the
    camera, and most of a palm apart when the hand is side-on. The picture landmarks sit on the
    fingertips, so fingers that meet there, neither well behind the other, are touching.
    """
    p = image[:, :2].astype(np.float64) * (aspect, 1.0)
    # The palm's length or, scaled to match, its width: whichever a turned hand has not foreshortened.
    palm = max(
        float(np.linalg.norm(p[MIDDLE_MCP] - p[WRIST])), 1.25 * float(np.linalg.norm(p[INDEX_MCP] - p[PINKY_MCP])), 1e-6
    )
    depth = abs(float(image[THUMB_TIP, 2] - image[INDEX_TIP, 2])) * aspect / palm
    if depth > _MAX_DEPTH_GAP:
        return math.inf
    return float(np.linalg.norm(p[THUMB_TIP] - p[INDEX_TIP])) / palm


def extract_features(hand: HandSample, aspect: float = 16 / 9) -> HandFeatures:
    """aspect is the camera frame's width over its height, which the picture landmarks are scaled by."""
    w = hand.world.astype(np.float64)
    palm_len = max(float(np.linalg.norm(w[MIDDLE_MCP] - w[WRIST])), 1e-4)
    curl, straight = [], []
    for mcp, pip, dip, tip in FINGERS:
        reach = float(np.linalg.norm(w[tip] - w[mcp]))
        bones = (
            float(np.linalg.norm(w[pip] - w[mcp]))
            + float(np.linalg.norm(w[dip] - w[pip]))
            + float(np.linalg.norm(w[tip] - w[dip]))
        )
        curl.append(reach / palm_len)
        straight.append(reach / max(bones, 1e-4))
    normal = np.cross(w[INDEX_MCP] - w[WRIST], w[PINKY_MCP] - w[WRIST])
    facing = abs(float(normal[2])) / max(float(np.linalg.norm(normal)), 1e-9)
    palm = hand.image[[WRIST, INDEX_MCP, PINKY_MCP], :2].mean(axis=0).astype(np.float64)
    pointing = (w[INDEX_TIP] - w[INDEX_MCP]) + (w[MIDDLE_TIP] - w[MIDDLE_MCP])
    thumb = w[THUMB_TIP]
    middle, ring = (float(np.linalg.norm(thumb - w[tip])) / palm_len for tip in (MIDDLE_TIP, RING_TIP))
    return HandFeatures(
        palm=palm,
        pinch_index=min(float(np.linalg.norm(thumb - w[INDEX_TIP])) / palm_len, _picture_pinch(hand.image, aspect)),
        pinch_pinky=float(np.linalg.norm(thumb - w[PINKY_TIP])) / palm_len,
        pinch_middle=middle,
        pinch_others=min(middle, ring),
        curl=tuple(curl),
        straight=tuple(straight),
        facing=facing,
        finger_tilt=math.degrees(math.atan2(-float(pointing[2]), -float(pointing[1]))),
    )


class PoseTracker:
    """Classifies each sample, then only switches pose once a candidate has persisted."""

    def __init__(self, cfg: PoseConfig):
        self.cfg = cfg
        self.pose = Pose.NEUTRAL
        self.since = 0.0  # when the current pose became stable
        self._candidate = Pose.NEUTRAL
        self._candidate_since = 0.0
        self._extended = [False, False, False, False]

    def _classify(self, f: HandFeatures) -> Pose:
        cfg = self.cfg
        fist_limit = cfg.fist_exit if self.pose is Pose.FIST else cfg.fist_enter
        if all(c < fist_limit for c in f.curl):
            return Pose.FIST

        if self.pose is Pose.PINCH_INDEX and f.pinch_index < cfg.pinch_exit:
            return Pose.PINCH_INDEX
        if self.pose is Pose.PINCH_MIDDLE and f.pinch_middle < cfg.pinch_exit:
            return Pose.PINCH_MIDDLE
        if self.pose is Pose.PINCH_PINKY and f.pinch_pinky < cfg.pinch_exit:
            return Pose.PINCH_PINKY
        if self.pose not in PINCHES:
            # The index pinch is the default. The pinky pinch has to win clearly over every other
            # finger, which also rules out the two-finger pose, where the thumb folds over the
            # ring finger and the pinky together.
            nearest_other = min(f.pinch_index, f.pinch_others)
            if f.pinch_pinky < cfg.pinch_enter and f.pinch_pinky * cfg.pinch_margin <= nearest_other:
                return Pose.PINCH_PINKY
            # The middle finger has to win as clearly, over the index finger above all, with the
            # ring finger and the pinky standing clear of it. A hand turned from the camera is not
            # read surely enough to tell: one pointing at the camera can look just like this.
            if (
                f.pinch_middle < _MIDDLE_PINCH_ENTER
                and f.facing >= cfg.turned_facing
                and f.pinch_middle <= f.pinch_others
                and f.pinch_middle * cfg.pinch_margin <= min(f.pinch_index, f.pinch_pinky)
                and min(f.straight[2:]) > _MIDDLE_PINCH_CLEAR
            ):
                return Pose.PINCH_MIDDLE
            if f.pinch_index < cfg.pinch_enter:
                return Pose.PINCH_INDEX

        for i, s in enumerate(f.straight):
            limit = cfg.extend_exit if self._extended[i] else cfg.extend_enter
            self._extended[i] = s > limit
        index, middle, ring, pinky = self._extended
        if index and middle and ring and pinky:
            return Pose.OPEN
        if index and middle and not ring and not pinky:
            return Pose.TWO_FINGER
        # A claw: every finger bent but none folded into the palm, and the thumb touching none of them.
        thumb = min(f.pinch_index, f.pinch_others, f.pinch_pinky)
        if self.pose is Pose.CLAW:
            # Turned like a knob, a claw reads looser: single fingers come out nearly straight and the
            # thumb nearer the fingertips. It is still a claw while its most bent finger is clearly
            # bent, which the 0.91 and up of an open or relaxed hand is not.
            if cfg.claw_min - 0.05 <= min(f.straight) <= _CLAW_STILL_BENT and min(f.curl) >= _CLAW_REACH - 0.04 and thumb > cfg.pinch_enter:
                return Pose.CLAW
        elif all(cfg.claw_min <= s <= cfg.claw_max for s in f.straight) and min(f.curl) >= _CLAW_REACH and thumb > cfg.claw_thumb:
            return Pose.CLAW
        return Pose.NEUTRAL

    def _hold_ms(self, candidate: Pose) -> float:
        cfg = self.cfg
        if self.pose in PINCHES:
            return cfg.pinch_off_ms
        if candidate in PINCHES:
            return cfg.pinch_on_ms
        if candidate is Pose.FIST:
            return cfg.fist_on_ms
        if candidate is Pose.CLAW:
            return cfg.claw_on_ms
        return cfg.pose_on_ms

    def update(self, f: HandFeatures, t: float, read: Pose | None = None) -> Pose:
        """read is the pose a model made of this sample; without one, the rules decide."""
        candidate = read if read is not None else self._classify(f)
        if candidate is self.pose:
            self._candidate = candidate
            return self.pose
        if candidate is not self._candidate:
            self._candidate, self._candidate_since = candidate, t
        if (t - self._candidate_since) * 1000.0 >= self._hold_ms(candidate):
            self.pose, self.since = candidate, t
        return self.pose

    def pinch_strength(self, f: HandFeatures) -> float:
        """0 when the fingers are apart at the exit threshold, 1 when fully closed."""
        cfg = self.cfg
        own = {Pose.PINCH_PINKY: f.pinch_pinky, Pose.PINCH_MIDDLE: f.pinch_middle}
        ratio = own.get(self.pose, min(f.pinch_index, f.pinch_pinky))
        closed = cfg.pinch_enter * 0.5
        span = max(cfg.pinch_exit * 1.6 - closed, 1e-6)
        return float(min(max((cfg.pinch_exit * 1.6 - ratio) / span, 0.0), 1.0))

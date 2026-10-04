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
    PINCH_PINKY = "pinch_pinky"
    FIST = "fist"
    TWO_FINGER = "two_finger"
    CLAW = "claw"
    AIM = "aim"  # pointing with the index finger, the thumb held out
    PRESS = "press"  # the same, with the thumb brought down onto the middle finger
    Y_SIGN = "y_sign"  # the letter Y of the manual alphabet: thumb and pinky out, the rest folded


PINCHES = (Pose.PINCH_INDEX, Pose.PINCH_PINKY)
HOLDS = (*PINCHES, Pose.PRESS)  # the poses that keep hold of something for as long as they last


@dataclass(slots=True)
class HandFeatures:
    palm: np.ndarray  # (2,) palm centre in mirrored-frame coordinates
    pinch_index: float  # thumb tip to index tip in palm lengths: the smaller of two ways of measuring it
    pinch_pinky: float
    pinch_others: float  # the middle or ring fingertip, whichever is nearer the thumb
    thumb_tuck: float  # thumb tip to the nearest part of the middle finger, in palm lengths
    curl: tuple[float, ...]  # fingertip-to-knuckle distance over palm length, index..pinky
    straight: tuple[float, ...]  # 1.0 = fully straight finger, index..pinky
    facing: float  # 1.0 when the palm plane is parallel to the image plane
    # Degrees the index and middle fingers lean from straight up toward the camera: 90 is pointing
    # at the camera, more is pointing down, negative is leaning back.
    finger_tilt: float


# Pointing: the index finger at least this straight, and the other three folded to this or under.
# Held up to point, the index finger measures 0.94 to 0.96 and the folded ones 0.46 to 0.60. The
# fingers of a claw are 0.63 to 0.80 all alike, and those of a relaxed hand 0.91 and up. A hand
# already pointing is given this much slack on both.
_POINT_STRAIGHT = 0.88
_POINT_FOLDED = 0.72
_POINT_SLACK = 0.07
# The letter Y: the pinky at least this straight and the other three fingers folded to this or
# under. Few hands can fold the ring finger right down beside a straight pinky, nor hold the pinky
# quite straight beside it, so both limits are looser than those for pointing.
_Y_STRAIGHT = 0.85
_Y_FOLDED = 0.75
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


def _to_segment(point: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    """How far the point is from the nearest part of the bone that runs from a to b."""
    bone = b - a
    along = min(max(float(np.dot(point - a, bone)) / max(float(np.dot(bone, bone)), 1e-12), 0.0), 1.0)
    return float(np.linalg.norm(point - (a + along * bone)))


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
    middle_finger = FINGERS[1]
    tuck = min(_to_segment(thumb, w[a], w[b]) for a, b in zip(middle_finger, middle_finger[1:])) / palm_len
    return HandFeatures(
        palm=palm,
        pinch_index=min(float(np.linalg.norm(thumb - w[INDEX_TIP])) / palm_len, _picture_pinch(hand.image, aspect)),
        pinch_pinky=float(np.linalg.norm(thumb - w[PINKY_TIP])) / palm_len,
        pinch_others=min(middle, ring),
        thumb_tuck=tuck,
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
        # A pinky reaches so little further straight than curled that the letter Y can pass for a
        # fist by how far its fingertips are from their knuckles. Its straight pinky tells them apart.
        signing_y = self._signing_y(f)
        if all(c < fist_limit for c in f.curl) and not signing_y:
            return Pose.FIST

        if self.pose is Pose.PINCH_INDEX and f.pinch_index < cfg.pinch_exit:
            return Pose.PINCH_INDEX
        if self.pose is Pose.PINCH_PINKY and f.pinch_pinky < cfg.pinch_exit:
            return Pose.PINCH_PINKY
        pointing = self._pointing(f)
        if self.pose is Pose.PRESS and pointing and f.thumb_tuck < cfg.pinch_exit:
            return Pose.PRESS
        if self.pose not in PINCHES:
            # The index pinch is the default. The pinky pinch has to win clearly over every other
            # finger, which also rules out the two-finger pose, where the thumb folds over the
            # ring finger and the pinky together.
            nearest_other = min(f.pinch_index, f.pinch_others)
            if f.pinch_pinky < cfg.pinch_enter and f.pinch_pinky * cfg.pinch_margin <= nearest_other:
                return Pose.PINCH_PINKY
            if f.pinch_index < cfg.pinch_enter:
                return Pose.PINCH_INDEX

        if pointing:
            # The thumb touches the middle finger, and leaves it, by the limits a pinch has.
            if self.pose is Pose.AIM:
                return Pose.PRESS if f.thumb_tuck < cfg.pinch_enter else Pose.AIM
            if self.pose is Pose.PRESS:
                return Pose.AIM
            # Only a thumb seen held out can come down to press. A hand that comes to point with
            # its thumb already tucked in is just pointing, and one turned from the camera is
            # not read surely enough to tell where its thumb is.
            if f.thumb_tuck > cfg.pinch_exit and f.facing >= cfg.turned_facing:
                return Pose.AIM
            return Pose.NEUTRAL
        if signing_y:
            # The thumb has to be out as well, well clear of the folded fingers, in a hand that
            # faces the camera. Once the sign is made it is the pinky that keeps it.
            if self.pose is Pose.Y_SIGN or (f.thumb_tuck > cfg.pinch_exit and f.facing >= cfg.turned_facing):
                return Pose.Y_SIGN
            return Pose.NEUTRAL

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

    def _pointing(self, f: HandFeatures) -> bool:
        """Whether the index finger is held out alone, the other three folded away."""
        slack = _POINT_SLACK if self.pose in (Pose.AIM, Pose.PRESS) else 0.0
        return f.straight[0] >= _POINT_STRAIGHT - slack and max(f.straight[1:]) <= _POINT_FOLDED + slack

    def _signing_y(self, f: HandFeatures) -> bool:
        """Whether the pinky is held out alone of the four fingers, the other three folded away."""
        slack = _POINT_SLACK if self.pose is Pose.Y_SIGN else 0.0
        return f.straight[3] >= _Y_STRAIGHT - slack and max(f.straight[:3]) <= _Y_FOLDED + slack

    def _hold_ms(self, candidate: Pose) -> float:
        cfg = self.cfg
        if self.pose in HOLDS:
            return cfg.pinch_off_ms
        if candidate in HOLDS:
            return cfg.pinch_on_ms
        if candidate is Pose.FIST:
            return cfg.fist_on_ms
        if candidate is Pose.CLAW:
            return cfg.claw_on_ms
        if candidate is Pose.Y_SIGN:
            return cfg.y_on_ms
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
        own = {Pose.PINCH_PINKY: f.pinch_pinky, Pose.AIM: f.thumb_tuck, Pose.PRESS: f.thumb_tuck}
        ratio = own.get(self.pose, min(f.pinch_index, f.pinch_pinky))
        closed = cfg.pinch_enter * 0.5
        span = max(cfg.pinch_exit * 1.6 - closed, 1e-6)
        return float(min(max((cfg.pinch_exit * 1.6 - ratio) / span, 0.0), 1.0))

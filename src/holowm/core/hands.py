"""Hand tracks: stable identity across frames, screen mapping, smoothing, pose and history."""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from pathlib import Path
from itertools import permutations

import numpy as np

from holowm.config import Config
from holowm.core.filters import MotionTrack, OneEuro
from holowm.core.pose_model import PoseModel
from holowm.core.poses import HOLDS, HandFeatures, Pose, PoseTracker, extract_features
from holowm.tracker.types import FrameSample, HandSample

_MATCH_GATE = 0.30  # max palm travel between frames, in frame widths
_HANDEDNESS_PENALTY = 0.15
_HISTORY_S = 0.6


def _spread(points: np.ndarray) -> float:
    """Root mean square distance of the points from their centre."""
    return float(np.sqrt(((points - points.mean(axis=0)) ** 2).sum(axis=1).mean()))


class Hand:
    """One tracked hand. Positions are screen pixels; ux/uy are not clamped to the screen."""

    def __init__(self, hand_id: int, cfg: Config, screen: tuple[int, int], sample: HandSample, t: float, model=None):
        self.id = hand_id
        self._model = model  # a PoseModel to read poses with, or None for the rules
        self.cfg = cfg
        self.screen = screen
        self.handedness = sample.handedness
        self.born = t
        self.last_seen = t
        self._aspect = cfg.camera.width / cfg.camera.height
        self.features: HandFeatures = extract_features(sample, self._aspect)
        self.landmarks = sample.image
        self._palm_raw = self.features.palm
        self._motion = MotionTrack(cfg.filter)
        self._fingers = OneEuro(cfg.filter.landmark_min_cutoff, cfg.filter.landmark_beta, cfg.filter.d_cutoff)
        self._poses = PoseTracker(cfg.pose)
        self.pose = Pose.NEUTRAL
        self.pose_since = t
        self.armed = False
        self.aimed = False  # has pointed, thumb out, for long enough that the thumb coming down is a press
        # Set once the current pinch/fist/two-finger pose has been acted on or rejected.
        self.consumed = False
        self.swipe_ready = True
        self.swipe_since = 0.0  # only motion after this time can count as a swipe
        self.x = self.y = self.ux = self.uy = 0.0
        self.pinch = 0.0
        self.history: deque[tuple[float, float, float]] = deque()
        self._ingest(sample, t)
        self.step(t)

    def _to_screen_units(self, palm: np.ndarray) -> np.ndarray:
        """Map a mirrored-frame point to screen-height units (y in 0..1, x in 0..aspect)."""
        m = self.cfg.mapping
        n = np.array([(palm[0] - m.box_x) / m.box_w, (palm[1] - m.box_y) / m.box_h])
        n = (n - 0.5) * (1.0 + 2.0 * m.overshoot) + 0.5
        w, h = self.screen
        return np.array([n[0] * w / h, n[1]])

    def _ingest(self, sample: HandSample, t: float) -> None:
        # Poses are read from smoothed finger landmarks. The palm position is taken raw, because
        # the motion track filters it itself.
        self.features = extract_features(replace(sample, world=self._fingers(sample.world, t)), self._aspect)
        self.landmarks = sample.image
        # The hand as it lies in the picture, in frame heights, and how large it appears there in
        # frame heights per metre. The nearer the camera it is, the larger it appears.
        self.frame_points = sample.image[:, :2].astype(np.float64) * (self._aspect, 1.0)
        self.image_scale = _spread(self.frame_points) / max(_spread(sample.world[:, :2]), 1e-4)
        self._palm_raw = self.features.palm
        self._motion.update(self._to_screen_units(self.features.palm), t)
        self.last_seen = t

    def update(self, sample: HandSample, t: float) -> None:
        self._ingest(sample, t)
        self.handedness = sample.handedness
        previous = self.pose
        read = self._model.classify(sample, self._aspect) if self._model is not None else None
        self.pose = self._poses.update(self.features, t, read)
        self.pinch = self._poses.pinch_strength(self.features)
        if self.pose is not previous:
            self.pose_since = t
            self.consumed = False
            cfg = self.cfg.pose
            turned = self.features.facing < cfg.turned_facing
            if self.pose in HOLDS and (
                not self.armed or self.speed > (cfg.turned_onset_speed if turned else cfg.max_onset_speed)
            ):
                self.consumed = True
            if self.pose is Pose.PRESS and not self.aimed:
                self.consumed = True
        if not self.armed and self.pose not in (*HOLDS, Pose.FIST):
            self.armed = (t - self.born) * 1000.0 >= self.cfg.pose.arm_ms
        # Aim once, and the thumb may go down and up any number of times.
        if self.pose is Pose.AIM:
            self.aimed = self.aimed or (t - self.pose_since) * 1000.0 >= self.cfg.pose.aim_ms
        elif self.pose is not Pose.PRESS:
            self.aimed = False

    @property
    def speed(self) -> float:
        """Filtered speed in screen heights per second."""
        return float(np.linalg.norm(self._motion.velocity))

    def step(self, now: float) -> None:
        h = self.screen[1]
        pos = self._motion.step(now) * h
        self.ux, self.uy = float(pos[0]), float(pos[1])
        self.x = min(max(self.ux, 0.0), self.screen[0] - 1.0)
        self.y = min(max(self.uy, 0.0), self.screen[1] - 1.0)
        self.history.append((now, self.ux, self.uy))
        while self.history and now - self.history[0][0] > _HISTORY_S:
            self.history.popleft()

    def peak_velocity(self, now: float, window_s: float, span_s: float = 0.05):
        """Fastest velocity (px/s) over the last window_s, and when it happened."""
        entries = [e for e in self.history if now - e[0] <= window_s + span_s]
        best, best_t, best_speed = (0.0, 0.0), now, 0.0
        j = 0
        for i, (t, x, y) in enumerate(entries):
            while j < i and t - entries[j + 1][0] >= span_s:
                j += 1
            t0, x0, y0 = entries[j]
            dt = t - t0
            if dt < span_s * 0.6:
                continue
            vx, vy = (x - x0) / dt, (y - y0) / dt
            speed = (vx * vx + vy * vy) ** 0.5
            if speed > best_speed:
                best, best_t, best_speed = (vx, vy), t, speed
        return best, best_t


class HandTracker:
    """Associates detections with existing hands so identities survive crossings and dropouts."""

    def __init__(self, cfg: Config, screen: tuple[int, int]):
        self.cfg = cfg
        self.screen = screen
        self.hands: dict[int, Hand] = {}
        self._next_id = 1
        self._model = None
        if cfg.pose.model:
            try:
                self._model = PoseModel.load(Path(cfg.pose.model).expanduser())
            except OSError as exc:
                raise ValueError(f"[pose] model: cannot read {cfg.pose.model} ({exc.strerror or exc})") from None

    def get(self, hand_id: int | None) -> Hand | None:
        return self.hands.get(hand_id) if hand_id is not None else None

    def update(self, frame: FrameSample) -> None:
        t = frame.t_capture
        detections = frame.hands[: self.cfg.tracker.num_hands]
        tracks = list(self.hands.values())
        palms = [extract_features(d).palm for d in detections]

        def cost(track: Hand, k: int) -> float:
            c = float(np.linalg.norm(track._palm_raw - palms[k]))
            if c > _MATCH_GATE:
                return float("inf")
            return c + (0.0 if track.handedness == detections[k].handedness else _HANDEDNESS_PENALTY)

        best_pairs: list[tuple[Hand, int]] = []
        best_cost = float("inf")
        n = min(len(tracks), len(detections))
        if n:
            for track_subset in permutations(tracks, n):
                for det_subset in permutations(range(len(detections)), n):
                    costs = [cost(tr, k) for tr, k in zip(track_subset, det_subset)]
                    total = sum(costs)
                    if total < best_cost:
                        best_cost = total
                        best_pairs = list(zip(track_subset, det_subset))
            if best_cost == float("inf"):
                # No full assignment within the gate; keep whichever single pairs are valid.
                best_pairs = []
                used: set[int] = set()
                for track in tracks:
                    options = [(cost(track, k), k) for k in range(len(detections)) if k not in used]
                    options = [o for o in options if o[0] != float("inf")]
                    if options:
                        _, k = min(options)
                        used.add(k)
                        best_pairs.append((track, k))

        matched = set()
        for track, k in best_pairs:
            track.update(detections[k], t)
            matched.add(k)
        for k, detection in enumerate(detections):
            if k not in matched and len(self.hands) < self.cfg.tracker.num_hands:
                hand = Hand(self._next_id, self.cfg, self.screen, detection, t, self._model)
                self.hands[hand.id] = hand
                self._next_id += 1

    def step(self, now: float) -> None:
        grace = self.cfg.filter.lost_grace_ms / 1000.0
        for hand_id in [i for i, h in self.hands.items() if now - h.last_seen > grace]:
            del self.hands[hand_id]
        for hand in self.hands.values():
            hand.step(now)

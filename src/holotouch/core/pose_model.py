"""A small network that reads the pose straight from the hand's landmarks, in place of the rules.

It is trained by `holotouch train` on recordings made by `holotouch collect`, and used only when
[pose] model in the configuration names the file it was saved to.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from holotouch.core.poses import Pose
from holotouch.tracker.types import INDEX_MCP, MIDDLE_MCP, PINKY_MCP, WRIST, HandSample

CLASSES = [Pose.OPEN, Pose.NEUTRAL, Pose.PINCH_INDEX, Pose.PINCH_PINKY, Pose.FIST, Pose.TWO_FINGER]


# The wrist, the fingertips, the knuckles, and the joint below each fingertip.
_KEY = [0, 4, 8, 12, 16, 20, 5, 9, 13, 17, 3, 6, 10, 14, 18]
_PAIRS = np.array([(a, b) for i, a in enumerate(_KEY) for b in _KEY[i + 1 :]])


def landmark_features(sample: HandSample, aspect: float) -> np.ndarray:
    """The hand's shape as the distances between its joints, in palm lengths: 210 numbers.

    Each distance is taken twice, in the metric landmarks and in the picture. Distances do not
    change with where the hand is, how large, which way it is turned or which hand it is, so a
    pose seen a few times is recognised again in a hand held differently.
    """
    world = sample.world.astype(np.float64)
    flat = sample.image[:, :2].astype(np.float64) * (aspect, 1.0)
    # The palm's length or, scaled to match, its width: whichever a turned hand has not foreshortened.
    palm = max(
        float(np.linalg.norm(flat[MIDDLE_MCP] - flat[WRIST])), 1.25 * float(np.linalg.norm(flat[INDEX_MCP] - flat[PINKY_MCP])), 1e-6
    )
    a, b = _PAIRS[:, 0], _PAIRS[:, 1]
    metric = np.linalg.norm(world[a] - world[b], axis=1) / max(float(np.linalg.norm(world[MIDDLE_MCP] - world[WRIST])), 1e-6)
    return np.concatenate([metric, np.linalg.norm(flat[a] - flat[b], axis=1) / palm])


class PoseModel:
    """One hidden layer. Its inputs are scaled by what the training data looked like."""

    def __init__(self, mean, scale, w1, b1, w2, b2, min_confidence: float = 0.6):
        self.mean, self.scale, self.w1, self.b1, self.w2, self.b2 = mean, scale, w1, b1, w2, b2
        self.min_confidence = min_confidence

    def probabilities(self, features: np.ndarray) -> np.ndarray:
        hidden = np.maximum((features - self.mean) / self.scale @ self.w1 + self.b1, 0.0)
        logits = hidden @ self.w2 + self.b2
        e = np.exp(logits - logits.max(axis=-1, keepdims=True))
        return e / e.sum(axis=-1, keepdims=True)

    def classify(self, sample: HandSample, aspect: float) -> Pose:
        """The pose this hand most looks like; neutral, which starts nothing, when it is not sure."""
        p = self.probabilities(landmark_features(sample, aspect))
        best = int(p.argmax())
        return CLASSES[best] if p[best] >= self.min_confidence else Pose.NEUTRAL

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, mean=self.mean, scale=self.scale, w1=self.w1, b1=self.b1, w2=self.w2, b2=self.b2,
                 classes=[c.value for c in CLASSES])  # fmt: skip

    @classmethod
    def load(cls, path: Path) -> "PoseModel":
        with np.load(path) as data:
            if list(data["classes"]) != [c.value for c in CLASSES]:
                raise ValueError(f"{path} was trained for other poses than this version reads")
            return cls(*(data[name] for name in ("mean", "scale", "w1", "b1", "w2", "b2")))


def train(x: np.ndarray, y: np.ndarray, hidden: int = 48, epochs: int = 400, seed: int = 0) -> PoseModel:
    """Fit a model to feature rows x and class indices y (into CLASSES)."""
    rng = np.random.default_rng(seed)
    mean, scale = x.mean(axis=0), x.std(axis=0) + 1e-3
    z = (x - mean) / scale
    targets = np.eye(len(CLASSES))[y]
    # Every pose counts the same however many frames of it there are.
    weight = (1.0 / np.maximum(np.bincount(y, minlength=len(CLASSES)), 1))[y]
    weight = weight / weight.sum()
    params = [rng.normal(0, np.sqrt(2.0 / z.shape[1]), (z.shape[1], hidden)), np.zeros(hidden),
              rng.normal(0, np.sqrt(2.0 / hidden), (hidden, len(CLASSES))), np.zeros(len(CLASSES))]  # fmt: skip
    moment, speed = [np.zeros_like(p) for p in params], [np.zeros_like(p) for p in params]
    for step in range(1, epochs + 1):
        w1, b1, w2, b2 = params
        noisy = z + rng.normal(0, 0.15, z.shape)  # a little jitter, so that it does not lean on any one landmark
        a = np.maximum(noisy @ w1 + b1, 0.0)
        logits = a @ w2 + b2
        p = np.exp(logits - logits.max(axis=1, keepdims=True))
        p /= p.sum(axis=1, keepdims=True)
        d_logits = (p - targets) * weight[:, None]
        d_a = d_logits @ w2.T * (a > 0)
        grads = [noisy.T @ d_a + 1e-4 * w1, d_a.sum(axis=0), a.T @ d_logits + 1e-4 * w2, d_logits.sum(axis=0)]
        for i, g in enumerate(grads):  # Adam
            moment[i] = 0.9 * moment[i] + 0.1 * g
            speed[i] = 0.999 * speed[i] + 0.001 * g * g
            params[i] = params[i] - 0.01 * (moment[i] / (1 - 0.9**step)) / (np.sqrt(speed[i] / (1 - 0.999**step)) + 1e-8)
    return PoseModel(mean, scale, *params)

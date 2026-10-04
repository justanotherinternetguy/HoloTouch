"""A small network that reads a letter of the American manual alphabet from one hand's landmarks.

It is used only while spelling (interactions/spell.py), never to tell the gestures apart: those
are read by the rules in poses.py. A model comes with HoloWM, trained on public landmarks by
research/letters_public.py; `holowm train-letters` makes one from those and your own hand
together, which is then used in its place.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from holowm.config import CONFIG_DIR
from holowm.tracker.types import INDEX_MCP, MIDDLE_MCP, PINKY_MCP, WRIST

# J and Z are drawn in the air, which one frame cannot show: their hands are those of I and of D.
LETTERS = "abcdefghiklmnopqrstuvwxy"
REST = "-"  # a hand that is spelling nothing, which a model has a class for if it was shown any

BUNDLED_PATH = Path(__file__).with_name("letters.npz")
# The public hands it was trained on (see letters_public.txt), which your own are added to.
PUBLIC_PATH = Path(__file__).with_name("letters_public.npz")
OWN_PATH = CONFIG_DIR / "letters.npz"  # where `holowm train-letters` saves, and what is used if it is there

# The wrist, the fingertips, the knuckles, and the joint below each fingertip.
_KEY = [0, 4, 8, 12, 16, 20, 5, 9, 13, 17, 3, 6, 10, 14, 18]
_PAIRS = np.array([(a, b) for i, a in enumerate(_KEY) for b in _KEY[i + 1 :]])


def letter_features(image: np.ndarray, aspect: float) -> np.ndarray:
    """One hand, or many at once, as 165 numbers: where each joint lies from the wrist, and how far apart they are.

    image is the hand's 21 picture landmarks, (21, 3) or (n, 21, 3), and aspect the picture's
    width over its height. Everything is in palm lengths, so it does not change with where the
    hand is or how large. It does change with which way the hand points, as it must: G is the
    hand of D lying on its side.
    """
    points = np.asarray(image, dtype=np.float64) * (aspect, 1.0, aspect)  # depth is on the scale of the width
    points = points - points[..., WRIST : WRIST + 1, :]
    knuckles = points[..., [INDEX_MCP, MIDDLE_MCP, PINKY_MCP], :]
    palm = np.maximum(np.linalg.norm(knuckles, axis=-1).mean(axis=-1), 1e-6)[..., None, None]
    points = points / palm
    a, b = _PAIRS[:, 0], _PAIRS[:, 1]
    apart = np.linalg.norm(points[..., a, :] - points[..., b, :], axis=-1)
    return np.concatenate([points[..., 1:, :].reshape(*points.shape[:-2], 60), apart], axis=-1)


class LetterModel:
    """One hidden layer. Its inputs are scaled by what the training data looked like."""

    def __init__(self, classes: str, mean, scale, w1, b1, w2, b2):
        self.classes = classes  # one character for each output: letters, and REST if it was trained on any
        self.mean, self.scale, self.w1, self.b1, self.w2, self.b2 = mean, scale, w1, b1, w2, b2

    def probabilities(self, features: np.ndarray) -> np.ndarray:
        hidden = np.maximum((features - self.mean) / self.scale @ self.w1 + self.b1, 0.0)
        logits = hidden @ self.w2 + self.b2
        e = np.exp(logits - logits.max(axis=-1, keepdims=True))
        return e / e.sum(axis=-1, keepdims=True)

    def read(self, image: np.ndarray, aspect: float) -> dict[str, float]:
        """How much this hand looks like each letter, the shares adding up to one."""
        return dict(zip(self.classes, self.probabilities(letter_features(image, aspect)).tolist()))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        weights = {name: getattr(self, name).astype(np.float32) for name in ("mean", "scale", "w1", "b1", "w2", "b2")}
        with open(path, "wb") as out:  # by handle, so that the name is kept as given
            np.savez_compressed(out, classes=np.array(self.classes), **weights)

    @classmethod
    def load(cls, path: Path) -> "LetterModel":
        with np.load(path) as data:
            return cls(str(data["classes"]), *(data[name].astype(np.float64) for name in ("mean", "scale", "w1", "b1", "w2", "b2")))


def public_hands() -> tuple[np.ndarray, np.ndarray]:
    """The public hands, as train() takes them, and the index into LETTERS of what each spells."""
    with np.load(PUBLIC_PATH) as data:
        return data["hands"].astype(np.float64), data["labels"].astype(int)


def model_path(configured: str = "") -> Path:
    """The model to spell with: the one [spell] model names, else your own, else the one HoloWM comes with."""
    if configured:
        return Path(configured).expanduser()
    return OWN_PATH if OWN_PATH.exists() else BUNDLED_PATH


def varied(images: np.ndarray, copies: int, rng: np.random.Generator) -> np.ndarray:
    """Each hand several times over, as another camera might have seen it, or the other hand made it.

    images is (n, 21, 3) with x already scaled by the picture's aspect, so that a turn is a turn.
    The copies come out in the same order, copy after copy: (copies * n, 21, 3). Each is turned a
    little in the picture, stretched a little sideways and in depth (the picture's shape and the
    scale of its depth are never known exactly), jittered, and half of them mirrored: the left
    hand spells what the right does, the other way round.
    """
    n = len(images)
    out = np.tile(images.astype(np.float64), (copies, 1, 1))
    out = out - out[:, WRIST : WRIST + 1]
    angle = np.radians(rng.uniform(-15.0, 15.0, copies * n))
    c, s = np.cos(angle)[:, None], np.sin(angle)[:, None]
    x, y = out[:, :, 0].copy(), out[:, :, 1].copy()
    out[:, :, 0], out[:, :, 1] = x * c - y * s, x * s + y * c
    out[:, :, 0] *= rng.uniform(0.85, 1.18, (copies * n, 1)) * rng.choice([-1.0, 1.0], (copies * n, 1))
    out[:, :, 2] *= rng.uniform(0.7, 1.3, (copies * n, 1))
    palm = np.linalg.norm(out[:, MIDDLE_MCP], axis=1)[:, None, None]
    return out + rng.normal(0.0, 0.02, out.shape) * palm


def train(
    images: np.ndarray, labels: np.ndarray, classes: str, hidden: int = 64, epochs: int = 300, copies: int = 12, seed: int = 0,
    weights: np.ndarray | None = None,
) -> LetterModel:  # fmt: skip
    """Fit a model to hands (n, 21, 3), x scaled by the aspect, and the index into classes of what each spells.

    weights says how much each hand counts beside the others of its letter; every letter counts
    the same however many hands of it there are.
    """
    rng = np.random.default_rng(seed)
    x = letter_features(varied(images, copies, rng), 1.0)
    y = np.tile(labels, copies)
    mean, scale = x.mean(axis=0), x.std(axis=0) + 1e-3
    z = (x - mean) / scale
    targets = np.eye(len(classes))[y]
    weight = np.tile(weights if weights is not None else np.ones(len(labels)), copies)
    weight = weight / np.maximum(np.bincount(y, weights=weight, minlength=len(classes)), 1e-9)[y]
    weight = weight / weight.sum()
    params = [rng.normal(0, np.sqrt(2.0 / z.shape[1]), (z.shape[1], hidden)), np.zeros(hidden),
              rng.normal(0, np.sqrt(2.0 / hidden), (hidden, len(classes))), np.zeros(len(classes))]  # fmt: skip
    moment, speed = [np.zeros_like(p) for p in params], [np.zeros_like(p) for p in params]
    for step in range(1, epochs + 1):
        w1, b1, w2, b2 = params
        a = np.maximum(z @ w1 + b1, 0.0)
        logits = a @ w2 + b2
        p = np.exp(logits - logits.max(axis=1, keepdims=True))
        p /= p.sum(axis=1, keepdims=True)
        d_logits = (p - targets) * weight[:, None]
        d_a = d_logits @ w2.T * (a > 0)
        grads = [z.T @ d_a + 1e-4 * w1, d_a.sum(axis=0), a.T @ d_logits + 1e-4 * w2, d_logits.sum(axis=0)]
        for i, g in enumerate(grads):  # Adam
            moment[i] = 0.9 * moment[i] + 0.1 * g
            speed[i] = 0.999 * speed[i] + 0.001 * g * g
            params[i] = params[i] - 0.01 * (moment[i] / (1 - 0.9**step)) / (np.sqrt(speed[i] / (1 - 0.999**step)) + 1e-8)
    return LetterModel(classes, mean, scale, *params)

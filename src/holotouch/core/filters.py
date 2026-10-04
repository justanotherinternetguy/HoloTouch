"""Jitter filtering and between-frame prediction for hand positions."""

from __future__ import annotations

import math

import numpy as np

from holotouch.config import FilterConfig


def _alpha(dt: float, cutoff):
    """Smoothing factor of a low-pass with this cutoff (Hz) at this sample interval."""
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuro:
    """1€ filter (Casiez, Roussel and Vogel, CHI 2012): a low-pass whose cutoff rises with speed.

    Slow movement is smoothed down to min_cutoff (Hz), which removes jitter; fast movement raises
    the cutoff by beta for each unit of speed, which removes lag. Takes a number, a point, or an
    array with one point per row. Each point gets its cutoff from its own speed, so a moving
    fingertip does not let the jitter of the still ones through.
    """

    def __init__(self, min_cutoff: float, beta: float, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x: np.ndarray | None = None
        self._dx: np.ndarray | None = None
        self._t = 0.0

    def reset(self) -> None:
        self._x = None

    def __call__(self, x, t: float) -> np.ndarray:
        x = np.array(x, dtype=np.float64)
        if self._x is None:
            self._x, self._dx, self._t = x, np.zeros_like(x), t
            return x
        dt = t - self._t
        if dt <= 0.0:  # not a new sample
            return self._x
        # The speed estimate is itself low-passed, measured from the last filtered value.
        self._dx = self._dx + _alpha(dt, self.d_cutoff) * ((x - self._x) / dt - self._dx)
        speed = np.linalg.norm(self._dx, axis=-1, keepdims=True) if x.ndim else np.abs(self._dx)
        self._x = self._x + _alpha(dt, self.min_cutoff + self.beta * speed) * (x - self._x)
        self._t = t
        return self._x


class MotionTrack:
    """Turns 30 Hz position samples into a smooth position at any tick time.

    Samples are One Euro filtered; a velocity estimate extrapolates the filtered position to the
    tick time (bounded, so a lost hand coasts to a stop), and a short exponential follow removes
    the small correction step when each new sample lands.
    """

    def __init__(self, cfg: FilterConfig):
        self.cfg = cfg
        self._filter = OneEuro(cfg.min_cutoff, cfg.beta, cfg.d_cutoff)
        self._pos: np.ndarray | None = None
        self._vel = np.zeros(2)
        self._t_sample = 0.0
        self._shown: np.ndarray | None = None
        self._t_shown = 0.0

    @property
    def velocity(self) -> np.ndarray:
        return self._vel

    def update(self, pos: np.ndarray, t: float) -> None:
        prev, prev_t = self._pos, self._t_sample
        filtered = self._filter(pos, t)
        if prev is not None:
            dt = max(t - prev_t, 1e-3)
            raw_vel = (filtered - prev) / dt
            self._vel = self._vel + _alpha(dt, self.cfg.velocity_cutoff) * (raw_vel - self._vel)
        self._pos, self._t_sample = filtered, t

    def predict(self, now: float) -> np.ndarray:
        lead = min(max(now - self._t_sample, 0.0), self.cfg.predict_max_ms / 1000.0)
        return self._pos + self._vel * lead

    def step(self, now: float) -> np.ndarray:
        target = self.predict(now)
        if self._shown is None:
            self._shown = target.copy()
        else:
            dt = max(now - self._t_shown, 0.0)
            tau = self.cfg.follow_tau_ms / 1000.0
            k = 1.0 if tau <= 0 else 1.0 - math.exp(-dt / tau)
            self._shown = self._shown + k * (target - self._shown)
        self._t_shown = now
        return self._shown

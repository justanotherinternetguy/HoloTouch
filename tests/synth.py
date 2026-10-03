"""Synthetic hands and a simulation harness, so the engine can be tested without a camera."""

from __future__ import annotations

import math
from typing import Callable

import numpy as np

from holowm.config import Config
from holowm.core.engine import Engine
from holowm.launcher.launch import Launcher
from holowm.launcher.menu import MenuItem
from holowm.tracker.types import FACE_CHEEKS, FACE_CHIN, FACE_FOREHEAD, FACE_OVAL, FaceSample, FrameSample, HandSample
from holowm.x11.fake import FakeBackend

_WRIST = (0.0, 0.04, 0.0)
_THUMB_BASE = [(-0.02, 0.02, -0.01), (-0.04, 0.0, -0.015), (-0.055, -0.02, -0.02)]
_MCPS = [(-0.025, -0.045, 0.0), (-0.005, -0.05, 0.0), (0.012, -0.045, 0.0), (0.028, -0.035, 0.0)]
_BONES = [(0.04, 0.025, 0.02), (0.045, 0.028, 0.02), (0.04, 0.026, 0.02), (0.032, 0.02, 0.018)]

# pose -> (curl per finger index..pinky, thumb tip position or the finger index it touches)
_POSES = {
    "open": ((0, 0, 0, 0), (-0.07, -0.04, -0.02)),
    "neutral": ((0.35, 0.35, 0.35, 0.35), (-0.07, -0.02, -0.02)),
    "pinch_index": ((0.45, 0, 0, 0), 0),
    "pinch_middle": ((0, 0.45, 0, 0), 1),
    "pinch_pinky": ((0, 0, 0, 0.45), 3),
    "fist": ((1, 1, 1, 1), (-0.02, -0.03, -0.04)),
    "two_finger": ((0, 0, 1, 1), (0.0, -0.02, -0.035)),
    "point": ((0, 1, 1, 1), (-0.07, -0.02, -0.02)),  # index only: no pose of its own, so neutral
    "claw": ((0.55, 0.55, 0.55, 0.55), (-0.07, -0.02, -0.02)),  # every finger bent, as if round a knob
    # How a fist pressed to the face tends to be read: fingers half hidden, thumb against the index.
    "loose_fist": ((0.66, 0.66, 0.66, 0.66), 0),
}
# Image coordinates per metre of world coordinates (x, y).
_IMAGE_SCALE = (1.2, 2.1)


def _finger(mcp, bones, curl, lean=0.0):
    points, pos, angle = [mcp], np.array(mcp, dtype=float), lean
    for length in bones:
        angle += curl * math.pi / 2
        pos = pos + length * np.array([0.0, -math.cos(angle), -math.sin(angle)])
        points.append(tuple(pos))
    return points


def world_landmarks(pose: str, tilt: float = 0.0) -> np.ndarray:
    """tilt leans the index and middle fingers toward the camera at the knuckle, in degrees."""
    curls, thumb = _POSES[pose]
    leans = [math.radians(tilt), math.radians(tilt), 0.0, 0.0]
    fingers = [_finger(m, b, c, lean) for m, b, c, lean in zip(_MCPS, _BONES, curls, leans)]
    if isinstance(thumb, int):
        tip = fingers[thumb][3]
        thumb = (tip[0] - 0.008, tip[1] + 0.005, tip[2])
    points = [_WRIST, *_THUMB_BASE, thumb]
    for finger in fingers:
        points.extend(finger)
    return np.array(points, dtype=np.float32)


def _palm_offset() -> np.ndarray:
    w = world_landmarks("open")
    return w[[0, 5, 17], :2].mean(axis=0) * np.array(_IMAGE_SCALE)


def make_hand(
    cfg: Config, screen, pose: str, x: float, y: float, handedness: str = "Right", tilt: float = 0.0, nearness: float = 1.0,
    roll: float = 0.0, yaw: float = 0.0,
) -> HandSample:  # fmt: skip
    """A hand whose palm centre maps to screen pixel (x, y).

    nearness is how much nearer the camera it is than usual, which makes it that much larger in
    the picture: 1.0 is the distance of the face that make_face draws. roll turns the hand about
    its palm, in degrees, clockwise as the picture shows it. yaw turns it about its upright axis,
    away from facing the camera: at 90 degrees it is side-on.
    """
    m = cfg.mapping
    n = np.array([x / screen[0], y / screen[1]])
    n = (n - 0.5) / (1.0 + 2.0 * m.overshoot) + 0.5
    palm = np.array([m.box_x + n[0] * m.box_w, m.box_y + n[1] * m.box_h])
    centre = palm - _palm_offset() * nearness
    world = world_landmarks(pose, tilt)
    if roll:
        c, s = math.cos(math.radians(roll)), math.sin(math.radians(roll))
        pivot = world[[0, 5, 17], :2].mean(axis=0)
        across, down = (world[:, :2] - pivot).T
        world[:, :2] = np.column_stack([across * c - down * s, across * s + down * c]) + pivot
    if yaw:
        c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        pivot = world[[0, 5, 17]][:, [0, 2]].mean(axis=0)
        across, depth = (world[:, [0, 2]] - pivot).T
        world[:, [0, 2]] = np.column_stack([across * c + depth * s, depth * c - across * s]) + pivot
    image = np.zeros((21, 3), dtype=np.float32)
    image[:, 0] = centre[0] + world[:, 0] * _IMAGE_SCALE[0] * nearness
    image[:, 1] = centre[1] + world[:, 1] * _IMAGE_SCALE[1] * nearness
    image[:, 2] = world[:, 2]
    return HandSample(handedness, 0.95, image, world)


def screen_point(cfg: Config, screen, u: float, v: float) -> tuple[float, float]:
    """The screen pixel a palm centre maps to when it is at (u, v) in the camera frame (0..1)."""
    m = cfg.mapping
    n = np.array([(u - m.box_x) / m.box_w, (v - m.box_y) / m.box_h])
    n = (n - 0.5) * (1.0 + 2.0 * m.overshoot) + 0.5
    return float(n[0] * screen[0]), float(n[1] * screen[1])


# Reference face size in metres (forehead to chin, cheek to cheek), as holowm.core.face assumes.
_FACE_M = (0.177, 0.153)


def make_face(cfg: Config, chin: tuple[float, float] = (0.5, 0.5)) -> FaceSample:
    """A face square to the camera with its chin at (u, v) in the frame, as far away as a nearness 1.0 hand."""
    aspect = cfg.camera.width / cfg.camera.height
    height, width = _FACE_M[0] * _IMAGE_SCALE[1], _FACE_M[1] * _IMAGE_SCALE[1] / aspect
    centre = np.array([chin[0], chin[1] - height / 2])
    image = np.zeros((478, 3), dtype=np.float32)
    image[:, :2] = centre
    for n, index in enumerate(FACE_OVAL):
        angle = 2 * math.pi * n / len(FACE_OVAL)
        image[index, :2] = centre + (math.sin(angle) * width / 2, -math.cos(angle) * height / 2)
    image[FACE_FOREHEAD, :2] = centre + (0, -height / 2)
    image[FACE_CHIN, :2] = chin
    image[FACE_CHEEKS[0], :2] = centre + (-width / 2, 0)
    image[FACE_CHEEKS[1], :2] = centre + (width / 2, 0)
    return FaceSample(image)


HandSpec = tuple  # (pose, x, y), then optionally handedness, finger tilt in degrees, nearness, and roll and yaw in degrees


class RecordingLauncher(Launcher):
    def __init__(self, backend, root: MenuItem):
        super().__init__(backend, root)
        self.activated: list[MenuItem] = []

    def activate(self, item, target):
        self.activated.append(item)
        super().activate(item, target)

    @staticmethod
    def _spawn(command, shell):
        pass


class Sim:
    """Feeds 30 Hz synthetic camera frames and 120 Hz ticks into an engine with a fake backend."""

    CAMERA_HZ = 30.0
    TICK_HZ = 120.0
    LATENCY = 0.03

    def __init__(self, cfg: Config | None = None, menu: MenuItem | None = None, screen=(2880, 1800)):
        self.cfg = cfg or Config()
        self.backend = FakeBackend(screen)
        self.launcher = RecordingLauncher(self.backend, menu or MenuItem("Root", children=[]))
        self.engine = Engine(self.cfg, self.backend, self.launcher)
        self.screen = screen
        self.face: FaceSample | None = None  # the face the camera sees, sent with every frame
        self.t = 100.0
        self._next_frame = self.t
        self._seq = 0

    def run(self, duration: float, hands: Callable[[float], list[HandSpec]] | None = None) -> None:
        """Advance time. hands(elapsed 0..1 fraction of this run) -> hand specs for a frame."""
        start, end = self.t, self.t + duration
        while self.t < end:
            if self.t >= self._next_frame:
                capture = self.t - self.LATENCY
                frac = min(max((capture - start) / duration, 0.0), 1.0)
                specs = hands(frac) if hands else []
                samples = [make_hand(self.cfg, self.screen, s[0], s[1], s[2], *s[3:]) for s in specs]
                self.engine.on_frame(FrameSample(self._seq, capture, self.t, samples, self.face))
                self._seq += 1
                self._next_frame += 1.0 / self.CAMERA_HZ
            self.engine.tick(self.t)
            self.t += 1.0 / self.TICK_HZ

    def hold(self, duration: float, *specs: HandSpec) -> None:
        self.run(duration, lambda _: list(specs))

    def glide(self, duration: float, pose: str, start, end, handedness: str = "Right") -> None:
        """Move one hand from start to end with smooth acceleration and deceleration."""

        def hands(frac: float):
            s = frac * frac * (3 - 2 * frac)
            return [(pose, start[0] + (end[0] - start[0]) * s, start[1] + (end[1] - start[1]) * s, handedness)]

        self.run(duration, hands)

    def commands(self, name: str) -> list[tuple]:
        return [c for c in self.backend.commands if c[0] == name]

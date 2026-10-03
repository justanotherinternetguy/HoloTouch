"""The face track, and the fist-to-chin touch on landmarks the real models produced for photos."""

import json
from pathlib import Path

import numpy as np
import pytest

from holowm.config import Config
from holowm.core.actions import WindowInfo
from holowm.core.engine import Engine
from holowm.core.face import FaceTrack
from holowm.core.hands import HandTracker
from holowm.tracker.types import FACE_CHEEKS, FaceSample, FrameSample, HandSample
from holowm.x11.fake import FakeBackend
from synth import make_face, make_hand, screen_point

SCREEN = (2880, 1800)
PHOTOS = json.loads((Path(__file__).parent / "fixtures/chin_photos.json").read_text())


def tracked(sample, cfg=None):
    tracker = HandTracker(cfg or Config(), SCREEN)
    tracker.update(FrameSample(0, 1.0, 1.0, [sample]))
    (hand,) = tracker.hands.values()
    return hand


def test_face_gives_the_chin_and_the_scale_of_the_picture():
    cfg = Config()
    face = FaceTrack(cfg)
    assert not face.visible(1.0)
    face.update(make_face(cfg, (0.4, 0.6)), 1.0)
    assert face.visible(1.0) and face.visible(2.0) and not face.visible(3.0)
    assert face.chin == pytest.approx((0.4 * 16 / 9, 0.6))  # in frame heights
    # make_hand draws a hand as far away as make_face draws the face.
    at_chin = screen_point(cfg, SCREEN, 0.4, 0.66)
    hand = tracked(make_hand(cfg, SCREEN, "fist", *at_chin))
    assert face.closeness(hand) == pytest.approx(1.0, abs=0.03) and face.reach(hand) < 0.1
    nearer = tracked(make_hand(cfg, SCREEN, "fist", *at_chin, nearness=1.7))
    assert face.closeness(nearer) == pytest.approx(1.7, abs=0.05)
    far_off = tracked(make_hand(cfg, SCREEN, "fist", *screen_point(cfg, SCREEN, 0.75, 0.3)))
    assert face.reach(far_off) > 1.0


@pytest.mark.parametrize("axis", [0, 1], ids=["turned", "nodding"])
def test_turning_or_nodding_does_not_make_the_face_look_further_away(axis):
    cfg = Config()
    straight, moved = FaceTrack(cfg), FaceTrack(cfg)
    sample = make_face(cfg)
    straight.update(sample, 1.0)
    squashed = sample.image.copy()
    centre = squashed[list(FACE_CHEEKS), axis].mean()
    squashed[:, axis] = centre + (squashed[:, axis] - centre) * 0.6  # that side of it looks 40% shorter
    moved.update(FaceSample(squashed), 1.0)
    assert moved.scale == pytest.approx(straight.scale, rel=0.02)


def test_recordings_keep_the_face_and_old_ones_still_load():
    cfg = Config()
    frame = FrameSample(3, 1.0, 1.02, [make_hand(cfg, SCREEN, "fist", 900, 700)], make_face(cfg))
    again = FrameSample.from_dict(json.loads(json.dumps(frame.to_dict())))
    assert again.face.image.shape == (478, 3)
    assert np.allclose(again.face.image, frame.face.image, atol=1e-4)
    old = frame.to_dict()
    del old["face"]
    assert FrameSample.from_dict(old).face is None and "face" not in FrameSample(0, 0.0, 0.0).to_dict()


@pytest.mark.parametrize("photo", PHOTOS, ids=[p["shows"] for p in PHOTOS])
def test_fist_on_chin_in_real_photos(photo):
    """Each photo played as a short video: the switcher must open exactly when a fist is on the chin."""
    cfg = Config()
    cfg.camera.width, cfg.camera.height = photo["size"]
    backend = FakeBackend(SCREEN)
    backend.add_window(WindowInfo(1, 100, 100, 800, 600, title="one"))
    engine = Engine(cfg, backend)
    points = np.zeros((478, 3), dtype=np.float32)
    for index, point in photo["face"].items():
        points[int(index)] = point
    hands = [
        HandSample(h["handedness"], h["score"], np.array(h["image"], np.float32), np.array(h["world"], np.float32))
        for h in photo["hands"]
    ]
    t, opened = 10.0, False
    for i in range(18):
        engine.on_frame(FrameSample(i, t, t, hands, FaceSample(points)))
        for _ in range(4):
            engine.tick(t)
            t += 1 / 120
            opened |= engine.overlay.switcher is not None
    assert opened == photo["touch"]
    assert not [c for c in backend.commands if c[0] in ("close", "move_resize", "activate")]

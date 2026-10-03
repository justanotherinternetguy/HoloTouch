"""Landmark samples passed from the tracker process to the core."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# MediaPipe hand landmark indices.
WRIST = 0
THUMB_TIP = 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20
FINGERS = (
    (INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP),
    (MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP),
    (RING_MCP, RING_PIP, RING_DIP, RING_TIP),
    (PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP),
)

# MediaPipe face mesh landmark indices.
FACE_FOREHEAD, FACE_CHIN = 10, 152
FACE_CHEEKS = (234, 454)
FACE_OVAL = (
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377,
    152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
)  # fmt: skip


@dataclass(slots=True)
class HandSample:
    # "Left" or "Right" as the hand looks in the frame. The frame is mirrored before inference,
    # so this is the user's other hand.
    handedness: str
    score: float
    image: np.ndarray  # (21, 3) normalised to the mirrored frame; x right, y down
    world: np.ndarray  # (21, 3) metres, origin at the hand's centre


@dataclass(slots=True)
class FaceSample:
    image: np.ndarray  # (478, 3) face mesh, normalised to the mirrored frame like a hand's


@dataclass(slots=True)
class FrameSample:
    seq: int
    t_capture: float  # time.monotonic() when the frame was grabbed
    t_result: float  # time.monotonic() when landmarks were ready
    hands: list[HandSample] = field(default_factory=list)
    # The face is looked for less often than the hands; None on frames without a fresh one.
    face: FaceSample | None = None

    def to_dict(self) -> dict:
        d = {
            "seq": self.seq,
            "t_capture": self.t_capture,
            "t_result": self.t_result,
            "hands": [
                {
                    "handedness": h.handedness,
                    "score": h.score,
                    # Rounded as float64, so each number is written with five decimals and no more.
                    "image": np.round(h.image.astype(float), 5).tolist(),
                    "world": np.round(h.world.astype(float), 5).tolist(),
                }
                for h in self.hands
            ],
        }
        if self.face is not None:
            d["face"] = np.round(self.face.image.astype(float), 4).tolist()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "FrameSample":
        return cls(
            seq=d["seq"],
            t_capture=d["t_capture"],
            t_result=d["t_result"],
            hands=[
                HandSample(
                    handedness=h["handedness"],
                    score=h["score"],
                    image=np.asarray(h["image"], dtype=np.float32),
                    world=np.asarray(h["world"], dtype=np.float32),
                )
                for h in d["hands"]
            ],
            face=FaceSample(np.asarray(d["face"], dtype=np.float32)) if d.get("face") else None,
        )

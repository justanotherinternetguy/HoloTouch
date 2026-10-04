"""A tracker process with no camera and no model: it sends empty samples, and saves a grey picture as each photo asked for."""

import time

import numpy as np

from holotouch.tracker.frames import save_photo
from holotouch.tracker.process import take_photos
from holotouch.tracker.types import FrameSample


def tracker_main(conn, cfg, frames_dir=None, requests=None) -> None:
    rgb = np.full((72, 128, 3), 128, dtype=np.uint8)
    seq = 0
    try:
        while True:
            now = time.monotonic()
            conn.send(FrameSample(seq, now, now, [], None))
            take_photos(requests, rgb, cfg.camera.mirror, conn.send, save_photo)
            seq += 1
            time.sleep(0.01)
    except (BrokenPipeError, OSError):
        pass

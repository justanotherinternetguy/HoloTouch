"""The tracker process: camera in, landmark samples out over a pipe.

Kept separate from the core so model inference never stalls the interaction loop, and so the
core can restart it if the camera or MediaPipe fails.
"""

from __future__ import annotations

import signal
import threading
import time
from pathlib import Path

from holotouch.config import Config
from holotouch.tracker.types import FrameSample

_IDLE_FACE_S = 0.5  # how often the face is looked for while no hands are in view


def take_photos(requests, rgb, mirrored: bool, send, save) -> None:
    """Save this frame wherever the core has asked for a photo since the last one, and tell it how that went.

    The core asks with {"photo": path}, and is told {"photo": path}, or {"photo": "", "problem": why}.
    """
    try:
        while requests.poll():
            path = Path(requests.recv()["photo"])
            try:
                save(rgb, path, mirrored)
            except (OSError, ValueError) as exc:
                send({"photo": "", "problem": f"{path}: {getattr(exc, 'strerror', None) or exc}"})
            else:
                send({"photo": str(path)})
    except (EOFError, OSError):
        pass  # the core has gone away


def tracker_main(conn, cfg: Config, frames_dir: Path | None = None, requests=None) -> None:
    """Entry point of the child process. Sends FrameSample objects, or {"error": ...} once.

    With frames_dir, every camera frame is also saved there as a picture. On `requests` the core
    asks for a photo: the frame then in hand is saved where it says.
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    send_lock = threading.Lock()
    last_hands = [time.monotonic()]
    alive = [True]

    def send(message) -> None:
        with send_lock:
            try:
                conn.send(message)
            except (BrokenPipeError, OSError):
                alive[0] = False  # the core has gone away

    def on_sample(sample: FrameSample) -> None:
        if sample.hands:
            last_hands[0] = sample.t_result
        send(sample)

    writer = snap = None
    try:
        from holotouch.tracker.camera import Camera
        from holotouch.tracker.landmarker import Landmarker

        if requests is not None:
            from holotouch.tracker.frames import save_photo

            def snap(rgb) -> None:
                take_photos(requests, rgb, cfg.camera.mirror, send, save_photo)

        camera = Camera(cfg.camera)
        landmarker = Landmarker(cfg.tracker, on_sample)
        if frames_dir is not None:
            from holotouch.tracker.frames import FrameWriter

            writer = FrameWriter(frames_dir)
            # Stop when asked instead of dying on the spot, so frames still waiting get written.
            signal.signal(signal.SIGTERM, lambda *_: alive.__setitem__(0, False))
    except Exception as exc:
        send({"error": f"{type(exc).__name__}: {exc}"})
        return

    try:
        error = pump(camera, landmarker, cfg, alive, last_hands, writer, snap)
        if error:
            send({"error": error})
    finally:
        if writer is not None:
            writer.close()
        landmarker.close()
        camera.close()


def pump(camera, landmarker, cfg: Config, alive: list[bool], last_hands: list[float], writer=None, snap=None) -> str | None:
    """Pass camera frames to the landmarker until alive[0] is cleared. Returns what went wrong, if anything.

    snap is shown every frame as it arrives, and saves it as a photo if one has been asked for.
    """
    frame_index = 0
    failures = 0
    last_face = 0.0
    while alive[0]:
        frame = camera.read()
        if frame is None:
            failures += 1
            if failures > 30:
                return "camera stopped delivering frames"
            time.sleep(0.02)
            continue
        failures = 0
        frame_index += 1
        if writer is not None:
            writer.save(*frame)  # every frame, including the ones skipped below
        if snap is not None:
            snap(frame[0])
        # With no hands in view, halve the inference rate to save power.
        now = time.monotonic()
        idle = now - last_hands[0] > cfg.tracker.idle_after_s
        if idle and frame_index % 2:
            continue
        # A face moves little, so it is looked for on only some of the frames.
        face = cfg.tracker.face and now - last_face >= (_IDLE_FACE_S if idle else 0.9 / cfg.tracker.face_hz)
        if face:
            last_face = now
        landmarker.submit(*frame, face=face)
    return None

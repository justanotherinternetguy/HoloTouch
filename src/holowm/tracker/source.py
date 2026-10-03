"""Where the core gets landmark samples from: the live tracker process, or a recording."""

from __future__ import annotations

import json
import logging
import multiprocessing
import time
from pathlib import Path

from holowm.config import Config
from holowm.tracker.types import FrameSample

log = logging.getLogger(__name__)

_RESTART_BACKOFF_S = 2.0
_STARTUP_GRACE_S = 8.0


class TrackerSource:
    """Runs the tracker in a child process and restarts it if it dies or stalls.

    With frames_dir, the tracker also saves every camera frame there.
    """

    def __init__(self, cfg: Config, frames_dir: Path | None = None):
        self.cfg = cfg
        self.frames_dir = frames_dir
        self.error: str | None = None
        self._context = multiprocessing.get_context("spawn")
        self._process = None
        self._conn = None
        self._started = 0.0
        self._last_message = 0.0
        self._suspended = False
        self._start()

    def _start(self) -> None:
        from holowm.tracker.process import tracker_main

        receiver, sender = self._context.Pipe(duplex=False)
        self._process = self._context.Process(target=tracker_main, args=(sender, self.cfg, self.frames_dir), daemon=True)
        self._process.start()
        sender.close()
        self._conn = receiver
        self._started = self._last_message = time.monotonic()

    def _stop_process(self) -> None:
        if self._process is not None:
            self._process.terminate()
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.kill()
        if self._conn is not None:
            self._conn.close()
        self._process = self._conn = None

    def suspend(self) -> None:
        """Stop tracking and let go of the camera, so that another program can use it."""
        if not self._suspended:
            self._suspended = True
            self._stop_process()

    def resume(self) -> None:
        """Start tracking again after suspend(). If the camera is still in use, drain() keeps trying."""
        if self._suspended:
            self._suspended = False
            self._start()

    def drain(self) -> list[FrameSample]:
        """All samples that arrived since the last call."""
        if self._suspended:
            return []
        now = time.monotonic()
        frames: list[FrameSample] = []
        try:
            while self._conn is not None and self._conn.poll():
                message = self._conn.recv()
                self._last_message = now
                if isinstance(message, FrameSample):
                    frames.append(message)
                    self.error = None
                elif isinstance(message, dict) and "error" in message:
                    if message["error"] != self.error:
                        log.error("tracker: %s", message["error"])
                    self.error = message["error"]
        except (EOFError, OSError):
            pass
        dead = self._process is None or not self._process.is_alive()
        stalled = (
            now - self._last_message > self.cfg.tracker.stall_restart_s
            and now - self._started > _STARTUP_GRACE_S
        )
        if (dead or stalled) and now - self._started > _RESTART_BACKOFF_S:
            log.warning("tracker %s; restarting", "exited" if dead else "stalled")
            self._stop_process()
            self._start()
        return frames

    def stop(self) -> None:
        self._stop_process()


class RecordingSource:
    """Passes another source's samples on, writing each one to a JSONL recording on the way."""

    def __init__(self, source, path: Path):
        self._source = source
        self.count = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        self._out = open(path, "w")

    @property
    def error(self) -> str | None:
        return self._source.error

    def drain(self) -> list[FrameSample]:
        frames = self._source.drain()
        for frame in frames:
            self._out.write(json.dumps(frame.to_dict()) + "\n")
        self.count += len(frames)
        return frames

    def suspend(self) -> None:
        self._source.suspend()

    def resume(self) -> None:
        self._source.resume()

    def stop(self) -> None:
        self._source.stop()
        self._out.close()


class ReplaySource:
    """Plays back a JSONL recording in real time, with timestamps rebased to now."""

    def __init__(self, path: Path, loop: bool = False):
        self.error: str | None = None
        self._frames = [FrameSample.from_dict(json.loads(line)) for line in path.read_text().splitlines() if line]
        self._loop = loop
        self._index = 0
        self._offset = time.monotonic() - (self._frames[0].t_result if self._frames else 0.0)

    @property
    def finished(self) -> bool:
        return self._index >= len(self._frames)

    def drain(self) -> list[FrameSample]:
        now = time.monotonic()
        out = []
        while self._index < len(self._frames) and self._frames[self._index].t_result + self._offset <= now:
            frame = self._frames[self._index]
            out.append(
                FrameSample(
                    frame.seq, frame.t_capture + self._offset, frame.t_result + self._offset, frame.hands, frame.face
                )
            )
            self._index += 1
        if self.finished and self._loop and self._frames:
            self._index = 0
            self._offset = now - self._frames[0].t_result + 0.5
        return out

    def suspend(self) -> None:
        pass  # a recording holds no camera

    def resume(self) -> None:
        pass

    def stop(self) -> None:
        pass

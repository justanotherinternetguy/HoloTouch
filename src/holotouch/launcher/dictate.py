"""Dictation: the microphone is recorded while it is wanted, and what was said is then typed.

Nothing here waits. The recorder and the program that turns its recording into text are separate
processes, looked in on every tick, so a slow one cannot stall the overlay.
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
import wave
from collections import deque
from pathlib import Path

from holotouch.config import RUNTIME_DIR, Config
from holotouch.core.actions import WindowBackend

log = logging.getLogger(__name__)

_RATE = 16000  # samples a second, of one channel, 16 bits each: what speech models take
# The recorders tried, in this order. Each writes bare samples to the file named after it, as
# they come, so nothing is lost when it is stopped. Left to itself parecord is handed the sound
# two seconds at a time, and what it has not been handed when it is stopped is gone.
_RECORDERS = (
    ("parecord", "--raw", "--format=s16le", f"--rate={_RATE}", "--channels=1", "--latency-msec=30", "--client-name=HoloTouch"),
    ("arecord", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(_RATE), "-c", "1"),
)
_SHORTEST_S = 0.3  # a recording shorter than this has nothing said in it
_FAILED_SHOWN_S = 2.0  # how long the overlay says that dictation could not be done


def recorder_command() -> tuple[str, ...] | None:
    """The program that records the microphone, with its arguments; None if none is installed."""
    return next((command for command in _RECORDERS if shutil.which(command[0])), None)


def transcriber_command(cfg: Config) -> str:
    """The shell command that turns {file} into text; empty if none is configured or installed."""
    if cfg.gesture.dictate_command:
        return cfg.gesture.dictate_command
    return "handy --transcribe-file {file} --json" if shutil.which("handy") else ""


def read_text(output: str) -> str:
    """What a transcriber printed, as the text that was said: its "text" field if it printed JSON."""
    try:
        said = json.loads(output)
    except ValueError:
        said = None
    text = said.get("text", "") if isinstance(said, dict) else output
    return " ".join(str(text).split())


class Dictation:
    """Call step() every tick with whether the microphone is wanted."""

    def __init__(self, cfg: Config, backend: WindowBackend):
        self.cfg = cfg
        self.backend = backend
        self._recorder: subprocess.Popen | None = None
        self._raw: Path | None = None  # what the recorder is writing
        self._refused = False  # it could not be started; not tried again until it is wanted afresh
        self._ending: deque[tuple[subprocess.Popen, Path]] = deque()  # recorders told to stop
        self._jobs: deque[tuple[subprocess.Popen, Path]] = deque()  # transcribers at work, oldest first
        self._failed_until = 0.0

    def step(self, wanted: bool, now: float) -> str:
        """What the overlay should say: "listening", "writing", "failed" or nothing."""
        if not wanted:
            self._refused = False
        if wanted and self._recorder is None and not self._refused:
            self._start(now)
        elif self._recorder is not None and (not wanted or self._recorder.poll() is not None):
            if wanted:  # it stopped by itself: no microphone, most likely
                log.warning("the recorder stopped by itself (exit status %s)", self._recorder.returncode)
                self._refused = True
            else:
                self._recorder.terminate()
            self._ending.append((self._recorder, self._raw))
            self._recorder = self._raw = None
        while self._ending and self._ending[0][0].poll() is not None:
            self._transcribe(self._ending.popleft()[1], now)
        # What was said first is typed first, however soon the one after it is ready.
        while self._jobs and self._jobs[0][0].poll() is not None:
            self._type(*self._jobs.popleft(), now)
        if now < self._failed_until:
            return "failed"
        if self._recorder is not None:
            return "listening"
        return "writing" if self._ending or self._jobs else ""

    def _fail(self, now: float, why: str, *args) -> None:
        log.warning(why, *args)
        self._failed_until = now + _FAILED_SHOWN_S

    def _start(self, now: float) -> None:
        recorder = recorder_command()
        if recorder is None or not transcriber_command(self.cfg):
            self._refused = True
            what = "parecord or arecord, to record the microphone" if recorder is None else "Handy, or dictate_command under [gesture]"
            self._fail(now, "cannot dictate: it needs %s", what)
            return
        handle, name = tempfile.mkstemp(prefix="holotouch-dictation-", suffix=".raw", dir=RUNTIME_DIR)
        os.close(handle)
        try:
            self._recorder = subprocess.Popen(
                [*recorder, name], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except OSError as exc:
            Path(name).unlink(missing_ok=True)
            self._refused = True
            self._fail(now, "cannot record the microphone: %s", exc)
            return
        self._raw = Path(name)
        log.info("dictation: recording the microphone")

    def _transcribe(self, raw: Path, now: float) -> None:
        samples = raw.read_bytes()
        raw.unlink(missing_ok=True)
        seconds = len(samples) / (2 * _RATE)
        if seconds < _SHORTEST_S:
            if self._refused:
                self._fail(now, "nothing was recorded: is there a microphone?")
            return
        sound = raw.with_suffix(".wav")
        with wave.open(str(sound), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(_RATE)
            out.writeframes(samples)
        command = transcriber_command(self.cfg).replace("{file}", shlex.quote(str(sound)))
        log.info("dictation: %.1f s recorded; turning it into text", seconds)
        try:
            job = subprocess.Popen(
                command, shell=True, text=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
        except OSError as exc:
            sound.unlink(missing_ok=True)
            self._fail(now, "cannot run %r: %s", command, exc)
            return
        self._jobs.append((job, sound))

    def _type(self, job: subprocess.Popen, sound: Path, now: float) -> None:
        output = job.stdout.read()
        job.stdout.close()
        sound.unlink(missing_ok=True)
        if job.returncode != 0:
            self._fail(now, "the transcriber failed (exit status %s)", job.returncode)
            return
        text = read_text(output)
        if not text:
            log.info("dictation: nothing was said")
            return
        log.info("dictation: typing %d characters", len(text))  # what was said is nobody's business but the text box's
        self.backend.type_text(text + (" " if self.cfg.gesture.dictate_trailing_space else ""))

    def close(self) -> None:
        """Stop at once: what is being recorded or turned into text is thrown away."""
        running = [(self._recorder, self._raw)] if self._recorder is not None else []
        for process, path in [*running, *self._ending, *self._jobs]:
            if process.poll() is None:
                process.kill()
            process.wait()
            if process.stdout is not None:
                process.stdout.close()
            path.unlink(missing_ok=True)
        self._recorder = self._raw = None
        self._ending.clear()
        self._jobs.clear()

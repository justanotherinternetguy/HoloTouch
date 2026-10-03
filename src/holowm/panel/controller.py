"""What the control panel knows and can do. The QML layer shows this and nothing else.

HoloWM runs as a process of its own, which the panel starts and then follows over the control
socket. So a HoloWM started some other way is found and controlled just the same, and closing
the panel leaves HoloWM running.
"""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot
from PySide6.QtNetwork import QLocalSocket

from holowm import __version__
from holowm.config import LOG_ENV, LOG_PATH, SOCKET_PATH, Config

log = logging.getLogger(__name__)

_POLL_MS = 400
_REPLY_MS = 1500  # a question not answered by now is taken to have no answer
_START_S = 20.0  # how long HoloWM has to come up before the start is given up
_QUIT_S = 3.0  # how long it has to go once asked to, before it is made to
_LOG_LINES = 300
_CHECK = re.compile(r"\[(ok  |warn|FAIL)\] (.*)")


def holowm_command(config: Path | None, *args: str) -> list[str]:
    """The command for `holowm ARGS` under this interpreter, which works with holowm off the PATH too."""
    command = [sys.executable, "-u", "-m", "holowm.cli"]
    if config is not None:
        command += ["--config", str(config)]
    return [*command, *args]


def parse_check(line: str) -> dict | None:
    """A line printed by `holowm doctor`, as the panel lists it. None if the line is not a check."""
    match = _CHECK.fullmatch(line.strip())
    if match is None:
        return None
    label, _, detail = match[2].partition(": ")
    return {"mark": match[1].strip().lower(), "label": label, "detail": detail}


class Controller(QObject):
    changed = Signal()
    logChanged = Signal()
    checksChanged = Signal()

    def __init__(
        self,
        cfg: Config,
        config_path: Path | None = None,
        scale: float | None = None,
        error: str = "",
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._cfg = cfg
        self._config_path = config_path
        self._scale = scale or cfg.ui.scale
        self._state = "stopped"  # stopped | starting | running | paused | stopping
        self._info: dict = {}  # what a running HoloWM last said of itself
        self._error = error
        self._debug = cfg.ui.debug
        self._practice = False
        self._proc: subprocess.Popen | None = None  # the HoloWM this panel started, if it did
        self._deadline = 0.0  # when a start or a stop has taken too long
        self._signal = signal.SIGTERM  # what a HoloWM that will not go is sent next
        self._asking = False
        self._log_path: Path | None = None
        self._log_offset = 0
        self._log_lines: list[str] = []
        self._checks: list[dict] = []
        self._doctor: QProcess | None = None
        self._doctor_output = ""  # what the doctor has printed of a line not yet finished
        self._doctor_said = ""  # the last line it printed
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.poll)

    def watch(self) -> None:
        """Begin following HoloWM. Needs a running event loop."""
        self._timer.start(_POLL_MS)
        self.poll()

    # -- constants ---------------------------------------------------------------------------

    @Property(float, constant=True)
    def scale(self) -> float:
        return self._scale

    @Property(str, constant=True)
    def accent(self) -> str:
        return self._cfg.ui.accent

    @Property(str, constant=True)
    def danger(self) -> str:
        return self._cfg.ui.danger

    @Property(str, constant=True)
    def version(self) -> str:
        return __version__

    # -- live state --------------------------------------------------------------------------

    @property
    def _up(self) -> bool:
        return self._state in ("running", "paused")

    @Property(str, notify=changed)
    def state(self) -> str:
        return self._state

    @Property(int, notify=changed)
    def fps(self) -> int:
        return int(self._info.get("fps", 0))

    @Property(int, notify=changed)
    def hands(self) -> int:
        return int(self._info.get("hands", 0))

    @Property(str, notify=changed)
    def gesture(self) -> str:
        return str(self._info.get("gesture", ""))

    @Property(bool, notify=changed)
    def lent(self) -> bool:
        """Paused only because the camera app has the webcam."""
        return bool(self._info.get("lent", False))

    @Property(str, notify=changed)
    def error(self) -> str:
        return self._error or str(self._info.get("error", ""))

    # A running HoloWM decides these two; the switches only say how the next one starts.
    @Property(bool, notify=changed)
    def debug(self) -> bool:
        return bool(self._info["debug"]) if "debug" in self._info else self._debug

    @Property(bool, notify=changed)
    def practice(self) -> bool:
        return bool(self._info["practice"]) if "practice" in self._info else self._practice

    @Property(str, notify=logChanged)
    def log(self) -> str:
        return "\n".join(self._log_lines)

    @Property("QVariantList", notify=checksChanged)
    def checks(self) -> list:
        return self._checks

    @Property(bool, notify=checksChanged)
    def checking(self) -> bool:
        return self._doctor is not None

    # -- starting and stopping ---------------------------------------------------------------

    @Slot()
    def start(self) -> None:
        if self._state != "stopped":
            return
        args = ["run", *(["--debug"] if self._debug else []), *(["--dry-run"] if self._practice else [])]
        try:
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_PATH, "wb") as out:
                # A session of its own, so that HoloWM outlives the panel and is not sent its signals.
                self._proc = subprocess.Popen(
                    holowm_command(self._config_path, *args),
                    stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                    start_new_session=True, env={**os.environ, LOG_ENV: str(LOG_PATH)},
                )  # fmt: skip
        except OSError as exc:
            self._error = f"HoloWM could not start: {exc}"
            self.changed.emit()
            return
        self._log_path, self._log_offset, self._log_lines = LOG_PATH, 0, []
        self.logChanged.emit()
        self._state, self._error = "starting", ""
        self._deadline = time.monotonic() + _START_S
        self._signal = signal.SIGTERM
        self.changed.emit()

    @Slot()
    def stop(self) -> None:
        if not self._up:
            return
        self._ask("quit", lambda reply: None)
        self._deadline = time.monotonic() + _QUIT_S
        self._state = "stopping"
        self._signal = signal.SIGTERM
        self.changed.emit()

    @Slot()
    def togglePause(self) -> None:
        if self._up:
            self._ask("toggle", self._on_toggled)

    def _on_toggled(self, reply: str | None) -> None:
        if reply in ("paused", "running") and self._up:
            self._state = reply
            self._info = {**self._info, "paused": reply == "paused", "lent": False}
            self.changed.emit()

    @Slot(bool)
    def setDebug(self, on: bool) -> None:
        self._debug = on
        if self._up and self._info.get("debug") != on:
            self._ask("debug", lambda reply: None)  # a running HoloWM only knows how to flip it
            self._info = {**self._info, "debug": on}
        self.changed.emit()

    @Slot(bool)
    def setPractice(self, on: bool) -> None:
        self._practice = on
        self.changed.emit()

    # -- following HoloWM --------------------------------------------------------------------

    def _ask(self, command: str, on_reply) -> None:
        """Send a command to the control socket. on_reply gets the answer, or None if there was none."""
        socket = QLocalSocket(self)
        answered = False

        def finish(reply: str | None) -> None:
            nonlocal answered
            if answered:
                return
            answered = True
            socket.abort()
            socket.deleteLater()
            on_reply(reply)

        def read() -> None:
            # Also tried when the socket fails: HoloWM hangs up as soon as it has answered.
            data = bytes(socket.readAll()) if socket.isOpen() else b""
            finish(data.decode(errors="replace").strip() or None)

        socket.connected.connect(lambda: socket.write(command.encode() + b"\n"))
        socket.readyRead.connect(read)
        socket.errorOccurred.connect(lambda error: read())
        QTimer.singleShot(_REPLY_MS, socket, lambda: finish(None))
        socket.connectToServer(str(SOCKET_PATH))

    def poll(self) -> None:
        self._read_log()
        if self._state in ("starting", "stopping") and time.monotonic() > self._deadline:
            self._kill()
        if not self._asking:
            self._asking = True
            self._ask("info", self._on_reply)

    def _on_reply(self, reply: str | None) -> None:
        self._asking = False
        try:
            info = json.loads(reply) if reply else None
        except ValueError:
            info = None
        self.on_info(info if isinstance(info, dict) else None)

    def on_info(self, info: dict | None) -> None:
        """Take in what HoloWM said of itself. None: nothing answered."""
        before = (self._state, self._info, self._error)
        if info is not None:
            if not self._up and info.get("log"):
                self._follow_log(Path(info["log"]))
            self._info = info
            if self._state != "stopping":
                if self._state == "stopped":
                    self._error = ""  # one that was started elsewhere, whatever went wrong here before
                self._state = "paused" if info.get("paused") else "running"
        elif self._state != "stopped" and not self._alive():
            code = self._proc.returncode if self._proc is not None else None
            if self._state == "starting":
                self._error = "HoloWM could not start. The Log tab says why."
            elif self._up and code not in (None, 0):
                self._error = "HoloWM stopped unexpectedly. The Log tab may say why."
            self._state, self._info, self._proc = "stopped", {}, None
            self._read_log()  # its last words
        if (self._state, self._info, self._error) != before:
            self.changed.emit()

    def _pid(self) -> int | None:
        return self._proc.pid if self._proc is not None else self._info.get("pid")

    def _alive(self) -> bool:
        """Whether the HoloWM being followed still exists. One that does not answer may only be busy."""
        if self._proc is not None:
            return self._proc.poll() is None
        try:
            os.kill(self._info["pid"], 0)
        except (KeyError, OSError):
            return False
        return True

    def _kill(self) -> None:
        pid = self._pid()
        if pid is None:
            return
        try:
            os.kill(pid, self._signal)
        except OSError:
            pass
        self._signal = signal.SIGKILL
        self._deadline = time.monotonic() + _QUIT_S

    # -- log ---------------------------------------------------------------------------------

    def _follow_log(self, path: Path) -> None:
        if path != self._log_path:
            self._log_path, self._log_offset, self._log_lines = path, 0, []
            self.logChanged.emit()

    def _read_log(self) -> None:
        if self._log_path is None:
            return
        try:
            with open(self._log_path, "rb") as fh:
                if fh.seek(0, os.SEEK_END) < self._log_offset:
                    self._log_offset, self._log_lines = 0, []  # it was started over
                fh.seek(self._log_offset)
                data = fh.read()
        except OSError:
            return
        # Only whole lines are taken; the start of an unfinished one is read again next time.
        end = data.rfind(b"\n") + 1
        if not end:
            return
        self._log_offset += end
        lines = data[:end].decode(errors="replace").splitlines()
        self._log_lines = (self._log_lines + lines)[-_LOG_LINES:]
        self.logChanged.emit()

    # -- checks ------------------------------------------------------------------------------

    @Slot()
    def runChecks(self) -> None:
        if self._doctor is not None:
            return
        doctor = QProcess(self)
        doctor.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        doctor.readyReadStandardOutput.connect(self._on_doctor_output)
        doctor.finished.connect(lambda code, status: self._on_doctor_done(code))
        doctor.errorOccurred.connect(
            lambda error: error == QProcess.ProcessError.FailedToStart and self._on_doctor_done(-1)
        )
        self._doctor, self._checks = doctor, []
        self._doctor_output = self._doctor_said = ""
        self.checksChanged.emit()
        # Without the tracking measurement, which needs the camera: HoloWM may be using it, and
        # the panel shows the frame rate of a running HoloWM anyway.
        command = holowm_command(self._config_path, "doctor", "--no-camera")
        doctor.start(command[0], command[1:])

    def _on_doctor_output(self) -> None:
        self._doctor_output += bytes(self._doctor.readAllStandardOutput()).decode(errors="replace")
        *lines, self._doctor_output = self._doctor_output.split("\n")
        self._doctor_said = next((line.strip() for line in reversed(lines) if line.strip()), self._doctor_said)
        checks = [check for check in map(parse_check, lines) if check is not None]
        if checks:
            self._checks = self._checks + checks
            self.checksChanged.emit()

    def _on_doctor_done(self, code: int) -> None:
        if self._doctor is None:
            return
        self._on_doctor_output()
        self._doctor.deleteLater()
        self._doctor = None
        if code not in (0, 1):  # the doctor's own two: all good, and problems found
            failure = {"mark": "fail", "label": "The checks could not be finished", "detail": self._doctor_said}
            self._checks = [*self._checks, failure]
        self.checksChanged.emit()

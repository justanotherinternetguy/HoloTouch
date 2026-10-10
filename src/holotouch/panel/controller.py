"""What the control panel knows and can do. The QML layer shows this and nothing else.

HoloTouch runs as a process of its own, which the panel starts and then follows over the control
socket. So a HoloTouch started some other way is found and controlled just the same, and closing
the panel leaves HoloTouch running.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot
from PySide6.QtNetwork import QLocalSocket

from holotouch import __version__
from holotouch.config import LOG_ENV, LOG_PATH, SOCKET_PATH, Config

log = logging.getLogger(__name__)

_POLL_MS = 400
_REPLY_MS = 1500  # a question not answered by now is taken to have no answer
_START_S = 20.0  # how long HoloTouch has to come up before the start is given up
_QUIT_S = 3.0  # how long it has to go once asked to, before it is made to
_LOG_LINES = 300
_CHECK = re.compile(r"\[(ok  |warn|FAIL)\] (.*)")
_BLIND_S = 5.0  # how long a running HoloTouch may deliver no frames before the camera is said to be missing
_PRACTICE_POLL_MS = 150  # practice mode watches for gestures, some of them brief

# What each of the doctor's checks is called when it is fine, what it is called when it is not,
# and what to do about that. Keyed on the doctor's own label, or on how the label starts.
_CHECKS = {
    "X11 session": (
        "X11 desktop session",
        "This isn't an X11 session",
        "HoloTouch needs one, or GNOME on Wayland. Log out and pick an Xorg session at the login screen.",
    ),
    "GNOME on Wayland": ("GNOME desktop on Wayland", "", ""),
    "GNOME Shell extension": (
        "GNOME Shell lets HoloTouch reach your windows",
        "GNOME Shell doesn't know HoloTouch yet",
        "On GNOME, HoloTouch moves windows and presses keys through an extension of its own. "
        "Run `holotouch gnome` in a terminal, then log out and back in.",
    ),
    "XWayland, which shows the overlay": (
        "Overlay can be drawn",
        "The overlay can't be drawn",
        "HoloTouch draws over your windows through XWayland, which GNOME starts by itself. This GNOME may have been built without it.",
    ),
    "smooth scrolling via GNOME Shell": ("Smooth scrolling", "", ""),
    "X server connection": (
        "X server answers",
        "The X server can't be reached",
        "HoloTouch needs a running X11 session to draw on.",
    ),
    "window manager supports the needed EWMH requests": (
        "Window manager works with HoloTouch",
        "This window manager can't do what HoloTouch asks",
        "HoloTouch is built for xfwm4, the XFCE window manager. The requests it lacks are listed below.",
    ),
    "X extension": (
        "",
        "An X extension is missing",
        "HoloTouch cannot run without it. It comes with any ordinary Xorg server.",
    ),
    "compositor running": (
        "Overlay can be see-through",
        "The overlay would hide your screen",
        "Compositing is off. Turn it on in Window Manager Tweaks, under Compositor.",
    ),
    "desktop background window": (
        "Desktop background is in place",
        "Moved windows will leave trails",
        "The desktop's own window is minimized. The line below gives the command that restores it.",
    ),
    "camera access": (
        "Camera can be opened",
        "HoloTouch isn't allowed to use the camera",
        "Give your user access to the device, usually by joining the video group, then log in again.",
    ),
    "camera mode": (
        "Camera offers the size asked for",
        "The camera doesn't list the size HoloTouch asks for",
        "HoloTouch will take what it is given. To choose a size the camera has, set width and height under [camera].",
    ),
    "camera app for the two-handed peace sign": (
        "Camera app for the peace sign",
        "The peace sign has nothing to open",
        "The camera app named as camera_command under [gesture] is not installed. Install it, or take "
        "that line out for HoloTouch to take the photo itself.",
    ),
    "dictation for the letter Y": (
        "Dictation for the letter Y",
        "The letter Y can't dictate yet",
        "It needs a recorder (parecord or arecord), xdotool to type (not on GNOME), and Handy to turn speech into text, "
        "or another program named as dictate_command under [gesture].",
    ),
    "macros to spell": (
        "Macros to spell",
        "Spelling has nothing to run",
        "macros.toml in ~/.config/holotouch, or the letter model named under [spell], cannot be used. "
        "The line below says what is wrong with it.",
    ),
    "apps to spell": (
        "Apps to spell by name",
        "The launcher can't open apps",
        "It opens them with gtk-launch, which comes with GTK 3. Macros can still be spelt.",
    ),
    "camera": (
        "Camera can be opened",
        "No camera found",
        "Plug a camera in, or set the device under [camera] in config.toml.",
    ),
    "hand tracking": (
        "Hand tracking is fast enough",
        "Tracking is too slow to feel right",
        "Close heavy programs, plug the laptop in, or lower the camera size under [camera].",
    ),
    "face tracking": (
        "Face is seen, for the chin gesture",
        "The window switcher won't open",
        "No face was seen, so a fist at the chin does nothing. Sit so the camera can see your face.",
    ),
    "smooth scrolling via /dev/uinput": (
        "Smooth scrolling",
        "Scrolling will move in steps",
        "HoloTouch can't write to /dev/uinput. Give your user write access to it for scrolling that glides.",
    ),
    "skipping tracks via playerctl": (
        "Music controls",
        "Music controls won't work yet",
        "The pie menu's Music petals need playerctl. Install it with your package manager.",
    ),
    "hand model": (
        "Hand model is downloaded",
        "The hand model will download on first start",
        "Nothing to do. The first start takes a little longer and needs the internet.",
    ),
    "face model": (
        "Face model is downloaded",
        "The face model will download on first start",
        "Nothing to do. The first start takes a little longer and needs the internet.",
    ),
}

# Practice mode: one thing to try at a time, on the two stand-in windows.
COACH = (
    {
        "name": "Grab",
        "title": "Grab a window",
        "body": "Hold a hand up, then touch your thumb to your index finger over one of the stand-in windows.",
        "praise": "Got it. You're holding the window.",
        "demo": "grab",
    },
    {
        "name": "Move",
        "title": "Carry it somewhere",
        "body": "Keep your fingers together and move your hand. Open them to let go.",
        "praise": "Moved it. That's how you carry any window.",
        "demo": "move",
    },
    {
        "name": "Resize",
        "title": "Resize it with both hands",
        "body": "Take hold of a stand-in window. Pinch with your other hand as well, then pull your hands apart.",
        "praise": "Resized. Either hand can let go first.",
        "demo": "resize",
    },
    {
        "name": "Pie menu",
        "title": "Open the pie menu",
        "body": "Touch your thumb to your little finger and hold. Move toward a petal, then let go to pick it.",
        "praise": "That's the menu. You're ready.",
        "demo": "menu",
    },
)


def holotouch_command(config: Path | None, *args: str) -> list[str]:
    """The command for `holotouch ARGS` under this interpreter, which works with holotouch off the PATH too."""
    command = [sys.executable, "-u", "-m", "holotouch.cli"]
    if config is not None:
        command += ["--config", str(config)]
    return [*command, *args]


def parse_check(line: str) -> dict | None:
    """A line printed by `holotouch doctor`, as the panel lists it. None if the line is not a check."""
    match = _CHECK.fullmatch(line.strip())
    if match is None:
        return None
    label, _, detail = match[2].partition(": ")
    return {"mark": match[1].strip().lower(), "label": label, "detail": detail}


def describe_check(check: dict) -> dict:
    """A check as the panel words it: a plain title, and for one that is not fine, what to do."""
    label, fine = check["label"], check["mark"] == "ok"
    known = _CHECKS.get(label) or next((said for start, said in _CHECKS.items() if label.startswith(start)), None)
    raw = f"[{check['mark']}] {label}" + (f": {check['detail']}" if check["detail"] else "")
    if known is None:
        return {**check, "title": label[:1].upper() + label[1:], "fix": "" if fine else check["detail"], "raw": raw}
    good, bad, fix = known
    return {**check, "title": (good or label) if fine else bad, "fix": "" if fine else fix, "raw": raw}


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
        state_path: Path | None = None,
    ):
        super().__init__(parent)
        self._cfg = cfg
        self._config_path = config_path
        self._scale = scale or cfg.ui.scale
        self._state = "stopped"  # stopped | starting | running | paused | stopping
        self._info: dict = {}  # what a running HoloTouch last said of itself
        self._error = error
        self._debug = cfg.ui.debug
        self._practice = False
        self._proc: subprocess.Popen | None = None  # the HoloTouch this panel started, if it did
        self._deadline = 0.0  # when a start or a stop has taken too long
        self._signal = signal.SIGTERM  # what a HoloTouch that will not go is sent next
        self._asking = False
        self._log_path: Path | None = None
        self._log_offset = 0
        self._log_lines: list[str] = []
        self._checks: list[dict] = []
        self._doctor: QProcess | None = None
        self._doctor_output = ""  # what the doctor has printed of a line not yet finished
        self._doctor_said = ""  # the last line it printed
        self._blind_since: float | None = None  # since when a running HoloTouch has delivered no frames
        self._then: bool | None = None  # once stopped, start again: in practice mode, or not
        self._step = 0  # the practice step being tried; len(COACH) once all are done
        self._praise = ""  # what is said of the step just done
        self._seen: dict = {}  # what the current step has noticed so far
        self._told = -1  # the step the overlay was last asked to show
        # What the panel remembers from one opening to the next. Without a path, nothing is kept.
        self._state_path = state_path
        self._kept = {"closeNoteSeen": False, "drawerOpen": False}
        if state_path is not None:
            try:
                self._kept.update({k: bool(v) for k, v in json.loads(state_path.read_text()).items() if k in self._kept})
            except (OSError, ValueError, AttributeError):
                pass
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.poll)

    def watch(self) -> None:
        """Begin following HoloTouch. Needs a running event loop."""
        self._timer.start(_POLL_MS)
        self.poll()

    # -- constants ---------------------------------------------------------------------------

    @Property(float, constant=True)
    def scale(self) -> float:
        return self._scale

    @Property("QVariantList", constant=True)
    def coach(self) -> list:
        return list(COACH)

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

    # A running HoloTouch decides these two; the switches only say how the next one starts.
    @Property(bool, notify=changed)
    def debug(self) -> bool:
        return bool(self._info["debug"]) if "debug" in self._info else self._debug

    @Property(bool, notify=changed)
    def practice(self) -> bool:
        return bool(self._info["practice"]) if "practice" in self._info else self._practice

    @Property(str, notify=logChanged)
    def log(self) -> str:
        return "\n".join(self._log_lines)

    @Property(str, notify=changed)
    def camera(self) -> str:
        """How the webcam is doing for a HoloTouch that is tracking: "ok", "waiting" or "missing"."""
        if self._state != "running" or self._blind_since is None:
            return "ok"
        if self._info.get("error") or time.monotonic() - self._blind_since >= _BLIND_S:
            return "missing"
        return "waiting"

    @Property(int, notify=changed)
    def coachStep(self) -> int:
        return self._step

    @Property(str, notify=changed)
    def coachPraise(self) -> str:
        return self._praise

    @Property(bool, notify=changed)
    def closeNoteSeen(self) -> bool:
        return self._kept["closeNoteSeen"]

    @Property(bool, notify=changed)
    def drawerOpen(self) -> bool:
        return self._kept["drawerOpen"]

    @Property("QVariantList", notify=checksChanged)
    def checks(self) -> list:
        return [describe_check(check) for check in self._checks]

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
                # A session of its own, so that HoloTouch outlives the panel and is not sent its signals.
                self._proc = subprocess.Popen(
                    holotouch_command(self._config_path, *args),
                    stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                    start_new_session=True, env={**os.environ, LOG_ENV: str(LOG_PATH)},
                )  # fmt: skip
        except OSError as exc:
            self._error = f"HoloTouch could not start: {exc}"
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
            self._ask("debug", lambda reply: None)  # a running HoloTouch only knows how to flip it
            self._info = {**self._info, "debug": on}
        self.changed.emit()

    @Slot(bool)
    def setPractice(self, on: bool) -> None:
        self._practice = on
        self.changed.emit()

    @Slot()
    def startPractice(self) -> None:
        self._begin(True)

    @Slot()
    def startForReal(self) -> None:
        self._begin(False)

    @Slot()
    def restart(self) -> None:
        """Stop HoloTouch and start it again the same way, as when the camera has come back."""
        if self._up:
            self._then = self.practice
            self.stop()

    @Slot()
    def copyLog(self) -> None:
        from PySide6.QtGui import QGuiApplication

        QGuiApplication.clipboard().setText(self.log)

    def _begin(self, practice: bool) -> None:
        """Start HoloTouch on stand-in windows or on real ones, stopping the other kind first if it is up."""
        if self._state == "stopped":
            self._practice = practice
            self.start()
        elif self._up and self.practice != practice:
            self._then = practice
            self.stop()

    # -- what the panel remembers ------------------------------------------------------------

    def _keep(self, key: str, value: bool) -> None:
        if self._kept[key] == value:
            return
        self._kept[key] = value
        if self._state_path is not None:
            try:
                self._state_path.parent.mkdir(parents=True, exist_ok=True)
                self._state_path.write_text(json.dumps(self._kept))
            except OSError as exc:
                log.warning("could not save the panel's state: %s", exc)
        self.changed.emit()

    @Slot()
    def dismissCloseNote(self) -> None:
        self._keep("closeNoteSeen", True)

    @Slot(bool)
    def setDrawerOpen(self, on: bool) -> None:
        self._keep("drawerOpen", on)

    # -- practice ----------------------------------------------------------------------------

    @Slot()
    def coachSkip(self) -> None:
        if self._step < len(COACH):
            self._advance("")

    @Slot()
    def coachRestart(self) -> None:
        self._step, self._praise, self._seen = 0, "", {}
        self._tell()
        self.changed.emit()

    def _advance(self, praise: str) -> None:
        self._step, self._praise, self._seen = self._step + 1, praise, {}
        self._tell()

    def _tell(self) -> None:
        """Have the overlay show the step being tried beside the stand-in windows, or nothing."""
        practising = self._up and self.practice
        step = self._step if practising and self._step < len(COACH) else -1
        if step == self._told or not self._up:
            return
        self._told = step
        if step < 0:
            self._ask("say", lambda reply: None)
            return
        said = {
            "caption": f"Practice · step {step + 1} of {len(COACH)}",
            "text": COACH[step]["title"],
            "detail": COACH[step]["body"],
            "progress": step / len(COACH),
        }
        self._ask("say " + json.dumps(said), lambda reply: None)

    def _watch_practice(self, info: dict) -> None:
        """Notice the step being tried getting done, from what a practising HoloTouch says of itself."""
        if self._step >= len(COACH) or info.get("paused"):
            return
        gesture, frame = info.get("gesture", ""), info.get("frame") or []
        mode = frame[0] if frame else ""
        held = gesture == "move" and mode in ("grab", "resize")
        seen = self._seen
        if self._step == 0:
            if held:
                self._advance(COACH[0]["praise"])
        elif self._step == 1:
            # Carried a good way across the screen, and then let go of.
            if held:
                x0, y0 = seen.setdefault("from", (frame[1], frame[2]))
                width = (info.get("screen") or [0])[0] or 1920
                seen["far"] = seen.get("far", False) or math.hypot(frame[1] - x0, frame[2] - y0) >= 0.15 * width
            elif seen.pop("far", False):
                self._advance(COACH[1]["praise"])
            else:
                seen.clear()
        elif self._step == 2:
            if mode == "resize":
                w0 = seen.setdefault("width", frame[3])
                if abs(frame[3] - w0) >= 0.2 * max(w0, 1):
                    self._advance(COACH[2]["praise"])
            else:
                seen.clear()
        elif gesture == "menu":
            seen["open"] = True
        elif seen.get("open"):
            self._advance(COACH[3]["praise"])

    # -- following HoloTouch --------------------------------------------------------------------

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
            # Also tried when the socket fails: HoloTouch hangs up as soon as it has answered.
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
        """Take in what HoloTouch said of itself. None: nothing answered."""
        before = (self._state, self._info, self._error, self.camera, self._step)
        if info is not None:
            if not self._up and info.get("log"):
                self._follow_log(Path(info["log"]))
            was_up = self._up
            self._info = info
            if self._state != "stopping":
                if self._state == "stopped":
                    self._error = ""  # one that was started elsewhere, whatever went wrong here before
                self._state = "paused" if info.get("paused") else "running"
            # A HoloTouch that is tracking but getting no frames has lost its camera, or never had it.
            blind = self._state == "running" and (bool(info.get("error")) or not info.get("fps"))
            self._blind_since = (self._blind_since or time.monotonic()) if blind else None
            if self._up and info.get("practice"):
                if not was_up:
                    self._step, self._praise, self._seen, self._told = 0, "", {}, -1  # a fresh practice
                self._watch_practice(info)
            self._tell()
        elif self._state != "stopped" and not self._alive():
            code = self._proc.returncode if self._proc is not None else None
            if self._state == "starting":
                self._error = "HoloTouch could not start. The log below says why."
            elif self._up and code not in (None, 0):
                self._error = "HoloTouch stopped unexpectedly. The log below may say why."
            self._state, self._info, self._proc = "stopped", {}, None
            self._blind_since, self._told = None, -1
            self._read_log()  # its last words
            if self._then is not None:
                # It was only stopped to be started again the other way.
                self._practice, self._then = self._then, None
                self.start()
        # Practice mode watches for gestures, some of them over in a moment.
        interval = _PRACTICE_POLL_MS if self._up and self.practice else _POLL_MS
        if self._timer.isActive() and self._timer.interval() != interval:
            self._timer.setInterval(interval)
        if (self._state, self._info, self._error, self.camera, self._step) != before:
            self.changed.emit()

    def _pid(self) -> int | None:
        return self._proc.pid if self._proc is not None else self._info.get("pid")

    def _alive(self) -> bool:
        """Whether the HoloTouch being followed still exists. One that does not answer may only be busy."""
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
        # Without the tracking measurement, which needs the camera: HoloTouch may be using it, and
        # the panel shows the frame rate of a running HoloTouch anyway.
        command = holotouch_command(self._config_path, "doctor", "--no-camera")
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

"""`holotouch doctor`: checks that this machine has what HoloTouch needs."""

from __future__ import annotations

import copy
import os
import shutil
import subprocess
import time
from pathlib import Path

from holotouch.config import Config

_EWMH_NEEDED = (
    "_NET_ACTIVE_WINDOW",
    "_NET_CLIENT_LIST_STACKING",
    "_NET_CLOSE_WINDOW",
    "_NET_CURRENT_DESKTOP",
    "_NET_FRAME_EXTENTS",
    "_NET_MOVERESIZE_WINDOW",
    "_NET_WM_DESKTOP",
    "_NET_WM_STATE_MAXIMIZED_VERT",
)


_ICONIC_STATE = 3
_RESTORE_DESKTOP = "xdotool windowmap $(xprop -root XFCE_DESKTOP_WINDOW | awk '{print $NF}')"


def _line(ok: bool | None, label: str, detail: str = "") -> bool:
    mark = {True: "ok  ", False: "FAIL", None: "warn"}[ok]
    print(f"[{mark}] {label}" + (f": {detail}" if detail else ""))
    return ok is not False


def _check_x11() -> bool:
    session = os.environ.get("XDG_SESSION_TYPE", "?")
    good = _line(session == "x11", "X11 session", session)
    try:
        from holotouch.x11.conn import X11

        x = X11()
    except Exception as exc:
        return _line(False, "X server connection", str(exc))
    supported = set(x.cardinals(x.reply(x.get_property(x.root, "_NET_SUPPORTED"))))
    missing = [name for name in _EWMH_NEEDED if x.atom(name) not in supported]
    good &= _line(not missing, "window manager supports the needed EWMH requests", ", ".join(missing))
    for extension in ("XTEST", "XFIXES", "SHAPE", "Composite", "RENDER"):
        present = x.core.QueryExtension(len(extension), extension).reply().present
        good &= _line(bool(present), f"X extension {extension}")
    owner = x.core.GetSelectionOwner(x.atom(f"_NET_WM_CM_S{x.conn.pref_screen}")).reply().owner
    _line(True if owner else None, "compositor running", "" if owner else "overlay will not be transparent")
    desktop = x.cardinals(x.reply(x.get_property(x.root, "XFCE_DESKTOP_WINDOW")))
    if desktop:
        # A minimized desktop window leaves nothing to repaint bare desktop, so moved windows leave trails.
        state = x.cardinals(x.reply(x.get_property(desktop[0], "WM_STATE")))
        minimized = bool(state) and state[0] == _ICONIC_STATE
        _line(
            None if minimized else True,
            "desktop background window",
            f"minimized, so windows leave trails on bare desktop; restore it with: {_RESTORE_DESKTOP}" if minimized else "",
        )
    x.conn.disconnect()
    return good


def _check_camera(cfg: Config, measure: bool) -> bool:
    device = Path(cfg.camera.device)
    if not device.exists():
        return _line(False, "camera", f"{device} does not exist")
    good = _line(os.access(device, os.R_OK | os.W_OK), "camera access", str(device))
    if shutil.which("v4l2-ctl"):
        formats = subprocess.run(
            ["v4l2-ctl", "-d", str(device), "--list-formats-ext"], capture_output=True, text=True
        ).stdout
        wanted = f"{cfg.camera.width}x{cfg.camera.height}"
        _line(True if wanted in formats else None, f"camera mode {wanted}", "" if wanted in formats else "not listed")
    if measure and good:
        good &= _measure_tracking(cfg)
    return good


def _measure_tracking(cfg: Config) -> bool:
    from holotouch.tracker.source import TrackerSource

    print("       measuring tracker for 6 s (the camera light will turn on)...")
    # Idle mode halves the rate when no hands are in view, which would skew the measurement.
    cfg = copy.deepcopy(cfg)
    cfg.tracker.idle_after_s = float("inf")
    source = TrackerSource(cfg)
    frames = []
    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline and not source.error:
        frames += source.drain()
        time.sleep(0.01)
    source.stop()
    if source.error or len(frames) < 10:
        return _line(False, "hand tracking", source.error or "no frames received")
    recent = frames[len(frames) // 3 :]
    span = recent[-1].t_capture - recent[0].t_capture
    fps = (len(recent) - 1) / span if span > 0 else 0.0
    inference = sorted(f.t_result - f.t_capture for f in recent)[len(recent) // 2] * 1000.0
    good = _line(fps >= 20, "hand tracking", f"{fps:.1f} fps, {inference:.0f} ms from capture to landmarks")
    if cfg.tracker.face:
        faces = sum(f.face is not None for f in recent)
        rate = faces / span if span > 0 else 0.0
        _line(
            True if faces else None,
            "face tracking",
            f"{rate:.0f} times a second" if faces else "no face seen, so touching a fist to the chin will do nothing",
        )
    return good


def run_doctor(cfg: Config, measure: bool = True) -> int:
    good = _check_x11()
    good &= _check_camera(cfg, measure)
    uinput = os.access("/dev/uinput", os.W_OK)
    _line(True if uinput else None, "smooth scrolling via /dev/uinput", "" if uinput else "falling back to XTEST steps")
    playerctl = shutil.which("playerctl") is not None
    _line(True if playerctl else None, "skipping tracks via playerctl", "" if playerctl else "not installed, so the pie menu's Music items do nothing")
    from holotouch.launcher.camera import camera_command

    camera = camera_command(cfg)
    _line(True if camera else None, "camera app for the two-handed peace sign", camera or "none found; set camera_command under [gesture]")
    from holotouch.launcher.dictate import recorder_command, transcriber_command

    missing = [
        what
        for what, there in (
            ("parecord or arecord, to record the microphone", recorder_command() is not None),
            ("Handy, or dictate_command under [gesture], to turn speech into text", bool(transcriber_command(cfg))),
            ("xdotool, to type it", shutil.which("xdotool") is not None),
        )
        if not there
    ]
    _line(None if missing else True, "dictation for the letter Y", "needs " + "; ".join(missing) if missing else "")
    from holotouch.config import MACROS_PATH
    from holotouch.core.letters import LetterModel, model_path
    from holotouch.launcher.apps import installed_apps
    from holotouch.launcher.macros import load_macros

    try:
        macros = load_macros()
        LetterModel.load(model_path(cfg.spell.model))
        spelt = ", ".join(macro.letters.upper() for macro in macros) or "none"
        _line(True if macros or cfg.spell.apps else None, "macros to spell", f"{spelt} ({MACROS_PATH if MACROS_PATH.exists() else 'built in'})")
    except Exception as exc:  # a macros.toml that will not load, or a file that is no letter model
        _line(None, "macros to spell", str(exc))
    if cfg.spell.apps:
        apps = len(installed_apps())
        opener = shutil.which("gtk-launch") is not None
        _line(True if apps and opener else None, "apps to spell", f"{apps} installed" if opener else "gtk-launch, which opens them, is not installed")
    from holotouch.tracker.landmarker import FACE_MODEL_PATH, MODEL_PATH

    for label, path in (("hand model", MODEL_PATH), ("face model", FACE_MODEL_PATH)):
        _line(True if path.exists() else None, label, str(path) if path.exists() else "will download on first run")
    print("all good" if good else "problems found")
    return 0 if good else 1

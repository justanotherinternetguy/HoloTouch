"""What the control panel makes of HoloWM and of the doctor. Needs no display, and starts no HoloWM."""

import os
import subprocess
import sys

from holowm.config import Config
from holowm.panel import controller, desktop
from holowm.panel.controller import Controller, parse_check


def info(**changes):
    said = {
        "pid": os.getpid(), "paused": False, "lent": False, "fps": 30, "hands": 2, "gesture": "move",
        "debug": True, "practice": False, "error": "", "log": "",
    }  # fmt: skip
    return {**said, **changes}


def gone_pid() -> int:
    """The pid of a process that has ended."""
    process = subprocess.Popen([sys.executable, "-c", ""])
    process.wait()
    return process.pid


def test_doctor_lines_become_checks():
    assert parse_check("[ok  ] X11 session: x11") == {"mark": "ok", "label": "X11 session", "detail": "x11"}
    assert parse_check("[ok  ] X extension XTEST") == {"mark": "ok", "label": "X extension XTEST", "detail": ""}
    failed = parse_check("[FAIL] camera: /dev/video9 does not exist\n")
    assert failed == {"mark": "fail", "label": "camera", "detail": "/dev/video9 does not exist"}
    assert parse_check("[warn] hand model: will download on first run")["mark"] == "warn"
    assert parse_check("all good") is None
    assert parse_check("       measuring tracker for 6 s (the camera light will turn on)...") is None


def test_panel_shows_what_a_running_holowm_says_of_itself():
    panel = Controller(Config())
    assert (panel.state, panel.fps, panel.debug) == ("stopped", 0, False)
    panel.on_info(info())
    assert (panel.state, panel.fps, panel.hands, panel.gesture) == ("running", 30, 2, "move")
    assert panel.debug is True  # the running one decides, not the panel's switch
    panel.on_info(info(paused=True, lent=True, error="camera stopped delivering frames"))
    assert (panel.state, panel.lent, panel.error) == ("paused", True, "camera stopped delivering frames")


def test_a_holowm_that_does_not_answer_is_only_gone_once_its_process_is():
    panel = Controller(Config())
    panel.on_info(info())
    panel.on_info(None)
    assert panel.state == "running"  # its process, this one, is still there: it may only be busy
    panel.on_info(info(pid=gone_pid()))
    panel.on_info(None)
    assert (panel.state, panel.fps, panel.error) == ("stopped", 0, "")


def test_a_start_that_fails_says_so_and_shows_the_log(tmp_path, monkeypatch):
    monkeypatch.setattr(controller, "LOG_PATH", tmp_path / "cache" / "holowm.log")
    monkeypatch.setattr(
        controller, "holowm_command", lambda config, *args: [sys.executable, "-c", f"raise SystemExit('no {args[0]}')"]
    )
    panel = Controller(Config(), error="left from before")
    panel.setPractice(True)
    panel.start()
    assert (panel.state, panel.error, panel.practice) == ("starting", "", True)
    panel._proc.wait()
    panel.on_info(None)
    assert panel.state == "stopped" and "could not start" in panel.error
    assert panel.log == "no run"


def test_desktop_entry_opens_the_panel_with_this_interpreter(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    path = desktop.install_launcher()
    assert path == tmp_path / "applications" / "holowm.desktop"
    lines = path.read_text().splitlines()
    assert f'Exec="{sys.executable}" -m holowm.cli panel' in lines
    assert f"Icon={desktop.ICON}" in lines and desktop.ICON.exists()

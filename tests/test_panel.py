"""What the control panel makes of HoloTouch and of the doctor. Needs no display, and starts no HoloTouch."""

import os
import subprocess
import sys

from holotouch.config import Config
from holotouch.panel import controller, desktop
from holotouch.panel.controller import COACH, Controller, describe_check, parse_check


def info(**changes):
    said = {
        "pid": os.getpid(), "paused": False, "lent": False, "fps": 30, "hands": 2, "gesture": "move",
        "debug": True, "practice": False, "error": "", "log": "", "frame": [], "screen": [1000, 800],
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


def test_panel_shows_what_a_running_holotouch_says_of_itself():
    panel = Controller(Config())
    assert (panel.state, panel.fps, panel.debug) == ("stopped", 0, False)
    panel.on_info(info())
    assert (panel.state, panel.fps, panel.hands, panel.gesture) == ("running", 30, 2, "move")
    assert panel.debug is True  # the running one decides, not the panel's switch
    panel.on_info(info(paused=True, lent=True, error="camera stopped delivering frames"))
    assert (panel.state, panel.lent, panel.error) == ("paused", True, "camera stopped delivering frames")


def test_a_holotouch_that_does_not_answer_is_only_gone_once_its_process_is():
    panel = Controller(Config())
    panel.on_info(info())
    panel.on_info(None)
    assert panel.state == "running"  # its process, this one, is still there: it may only be busy
    panel.on_info(info(pid=gone_pid()))
    panel.on_info(None)
    assert (panel.state, panel.fps, panel.error) == ("stopped", 0, "")


def test_a_start_that_fails_says_so_and_shows_the_log(tmp_path, monkeypatch):
    monkeypatch.setattr(controller, "LOG_PATH", tmp_path / "cache" / "holotouch.log")
    monkeypatch.setattr(
        controller, "holotouch_command", lambda config, *args: [sys.executable, "-c", f"raise SystemExit('no {args[0]}')"]
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
    assert path == tmp_path / "applications" / "holotouch.desktop"
    lines = path.read_text().splitlines()
    assert f'Exec="{sys.executable}" -m holotouch.cli panel' in lines
    assert f"Icon={desktop.ICON}" in lines and desktop.ICON.exists()


def test_checks_are_worded_for_people_and_say_what_to_do():
    fine = describe_check(parse_check("[ok  ] compositor running"))
    assert fine["title"] == "Overlay can be see-through" and fine["fix"] == ""
    missing = describe_check(parse_check("[FAIL] camera: /dev/video9 does not exist"))
    assert missing["title"] == "No camera found" and "config.toml" in missing["fix"]
    assert missing["raw"] == "[fail] camera: /dev/video9 does not exist"  # the doctor's own words stay to hand
    barred = describe_check(parse_check("[FAIL] camera access: /dev/video0"))
    assert barred["title"] == "HoloTouch isn't allowed to use the camera"
    assert describe_check(parse_check("[warn] camera mode 1280x720: not listed"))["title"].startswith("The camera doesn't list")
    assert describe_check(parse_check("[ok  ] X extension XTEST"))["title"] == "X extension XTEST"
    # A check the panel has no words for is shown as the doctor put it.
    new = describe_check(parse_check("[warn] something new: went oddly"))
    assert (new["title"], new["fix"]) == ("Something new", "went oddly")


def test_a_running_holotouch_with_no_frames_is_waiting_for_the_camera_then_missing_it(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(controller.time, "monotonic", lambda: clock[0])
    panel = Controller(Config())
    panel.on_info(info())
    assert panel.camera == "ok"
    panel.on_info(info(fps=0))
    assert panel.camera == "waiting"
    clock[0] += 6.0
    panel.on_info(info(fps=0))
    assert panel.camera == "missing"
    panel.on_info(info(fps=28))
    assert panel.camera == "ok"
    panel.on_info(info(fps=0, error="camera stopped delivering frames"))
    assert panel.camera == "missing"  # it said so itself: no need to wait
    panel.on_info(info(fps=0, paused=True))
    assert panel.camera == "ok"  # paused is not blind


def test_practice_goes_one_step_at_a_time_and_tells_the_overlay(monkeypatch):
    said = []
    monkeypatch.setattr(Controller, "_ask", lambda self, command, on_reply: said.append(command))
    panel = Controller(Config())
    practising = lambda **changes: info(**{"practice": True, "gesture": "", **changes})  # noqa: E731
    panel.on_info(practising())
    assert panel.coachStep == 0 and said[-1].startswith("say {") and COACH[0]["title"] in said[-1]
    # 1: grab a window.
    panel.on_info(practising(gesture="move", frame=["grab", 100, 100, 400, 300]))
    assert (panel.coachStep, panel.coachPraise) == (1, COACH[0]["praise"])
    # 2: carry it a good way, then let go. A small nudge is not enough.
    panel.on_info(practising(gesture="move", frame=["grab", 120, 100, 400, 300]))
    panel.on_info(practising())
    assert panel.coachStep == 1
    panel.on_info(practising(gesture="move", frame=["grab", 100, 100, 400, 300]))
    panel.on_info(practising(gesture="move", frame=["grab", 300, 100, 400, 300]))
    assert panel.coachStep == 1  # still holding it
    panel.on_info(practising())
    assert panel.coachStep == 2
    # 3: both hands, and the size has to change.
    panel.on_info(practising(gesture="move", frame=["resize", 300, 100, 400, 300]))
    panel.on_info(practising(gesture="move", frame=["resize", 280, 90, 500, 380]))
    assert panel.coachStep == 3 and COACH[3]["title"] in said[-1]
    # 4: the menu, opened and then closed.
    panel.on_info(practising(gesture="menu"))
    assert panel.coachStep == 3
    panel.on_info(practising())
    assert panel.coachStep == len(COACH) and said[-1] == "say"  # done: the line on the desktop goes
    panel.coachRestart()
    assert panel.coachStep == 0 and panel.coachPraise == ""
    panel.coachSkip()
    assert panel.coachStep == 1 and panel.coachPraise == ""


def test_the_panel_remembers_what_it_was_told_between_openings(tmp_path):
    path = tmp_path / "cache" / "panel.json"
    panel = Controller(Config(), state_path=path)
    assert not panel.closeNoteSeen and not panel.drawerOpen
    panel.dismissCloseNote()
    panel.setDrawerOpen(True)
    again = Controller(Config(), state_path=path)
    assert again.closeNoteSeen and again.drawerOpen
    assert not Controller(Config()).closeNoteSeen  # with no path, nothing is kept or read

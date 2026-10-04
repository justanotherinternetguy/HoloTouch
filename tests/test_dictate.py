"""Dictation, with stand-ins for the recorder and for the program that turns speech into text."""

import sys
import time

import pytest

from holotouch.config import Config
from holotouch.launcher import dictate
from holotouch.launcher.dictate import Dictation, read_text
from holotouch.x11.fake import FakeBackend

# Writes `seconds` of silence to the file it is given, as a recorder writes what it hears, then waits to be stopped.
_RECORDER = "import sys, time; f = open(sys.argv[2], 'wb'); f.write(bytes(int(32000 * float(sys.argv[1])))); f.flush(); time.sleep(60)"


@pytest.fixture
def kit(tmp_path, monkeypatch):
    """A dictation whose recorder hears two seconds at once, and whose transcriber says the same thing every time."""
    monkeypatch.setattr(dictate, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(dictate, "_RECORDERS", ((sys.executable, "-c", _RECORDER, "2"),))
    cfg, backend = Config(), FakeBackend()
    cfg.gesture.dictate_command = "test -s {file} && echo '  hello   world. '"
    kit = Dictation(cfg, backend)
    yield kit
    kit.close()


def until(kit, wanted, state, timeout=5.0):
    """Step until the dictation says `state`, and return every state it said on the way."""
    said, deadline = [], time.monotonic() + timeout
    while time.monotonic() < deadline:
        now = kit.step(wanted, time.monotonic())
        if not said or said[-1] != now:
            said.append(now)
        if now == state:
            return said
        time.sleep(0.01)
    raise AssertionError(f"never said {state!r}: {said}")


def recorded(kit):
    """Wait for the stand-in recorder to have written what it hears."""
    deadline = time.monotonic() + 5.0
    while not kit._raw.stat().st_size and time.monotonic() < deadline:
        time.sleep(0.01)


def test_what_is_said_while_the_microphone_is_wanted_is_typed_once_it_no_longer_is(kit, tmp_path):
    assert kit.step(False, time.monotonic()) == ""
    assert until(kit, True, "listening") == ["listening"]
    recorded(kit)
    assert not kit.backend.commands
    assert until(kit, False, "") == ["writing", ""]
    assert kit.backend.commands == [("type_text", "hello world. ")]
    assert not list(tmp_path.iterdir())  # nothing that was said is kept


def test_no_space_follows_what_was_said_when_none_is_asked_for(kit):
    kit.cfg.gesture.dictate_trailing_space = False
    until(kit, True, "listening")
    recorded(kit)
    until(kit, False, "")
    assert kit.backend.commands == [("type_text", "hello world.")]


def test_what_is_said_first_is_typed_first(kit):
    # The first takes a while to be turned into text; the second is ready at once.
    kit.cfg.gesture.dictate_command = "test -e {file} && sleep 0.4 && echo first"
    until(kit, True, "listening")
    recorded(kit)
    while not kit._jobs:  # the recorder has stopped, and the first is being turned into text
        assert kit.step(False, time.monotonic()) == "writing"
    kit.cfg.gesture.dictate_command = "test -e {file} && echo second"
    until(kit, True, "listening")
    recorded(kit)
    until(kit, False, "")
    assert kit.backend.commands == [("type_text", "first "), ("type_text", "second ")]


def test_a_sign_dropped_at_once_types_nothing(kit, monkeypatch, tmp_path):
    monkeypatch.setattr(dictate, "_RECORDERS", ((sys.executable, "-c", _RECORDER, "0.1"),))
    until(kit, True, "listening")
    recorded(kit)
    until(kit, False, "")
    assert not kit.backend.commands and not list(tmp_path.iterdir())


def test_silence_types_nothing(kit):
    kit.cfg.gesture.dictate_command = "true {file}"
    until(kit, True, "listening")
    recorded(kit)
    assert until(kit, False, "") == ["writing", ""]
    assert not kit.backend.commands


def test_a_transcriber_that_fails_says_so_and_types_nothing(kit, tmp_path):
    kit.cfg.gesture.dictate_command = "echo half a sentence; false {file}"
    until(kit, True, "listening")
    recorded(kit)
    assert until(kit, False, "failed")[-1] == "failed"
    assert not kit.backend.commands and not list(tmp_path.iterdir())


def test_without_a_recorder_or_a_transcriber_it_says_so_once_and_does_not_keep_trying(kit, monkeypatch, tmp_path):
    monkeypatch.setattr(dictate, "_RECORDERS", (("no-such-recorder",),))
    assert kit.step(True, 10.0) == "failed"
    assert kit.step(True, 11.0) == "failed" and kit.step(True, 12.5) == ""  # the note goes away; it is not tried again
    assert kit.step(False, 13.0) == "" and kit.step(True, 13.1) == "failed"  # until the sign is made afresh
    monkeypatch.undo()
    monkeypatch.setattr(dictate, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(dictate.shutil, "which", lambda name: None if name == "handy" else "/usr/bin/" + name)
    kit.cfg.gesture.dictate_command = ""
    assert kit.step(False, 20.0) == "" and kit.step(True, 20.1) == "failed"
    assert not kit.backend.commands and not list(tmp_path.iterdir())


def test_a_recorder_that_stops_by_itself_is_a_failure_to_dictate(kit, monkeypatch):
    monkeypatch.setattr(dictate, "_RECORDERS", ((sys.executable, "-c", "raise SystemExit(1)"),))
    assert "failed" in until(kit, True, "failed")
    assert not kit.backend.commands


def test_closing_throws_away_what_is_being_recorded(kit, tmp_path):
    until(kit, True, "listening")
    recorded(kit)
    kit.close()
    assert not kit.backend.commands and not list(tmp_path.iterdir())
    assert kit.step(False, time.monotonic()) == ""


def test_text_is_read_from_json_or_as_it_is_printed():
    assert read_text('{"audio_secs": 5.4, "text": " Hello world.\\n"}') == "Hello world."
    assert read_text("Hello\n  world.\n") == "Hello world."
    assert read_text('{"error": "no model"}') == "" and read_text("") == ""

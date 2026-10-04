"""Sending the page to the phone, with stand-ins for the clipboard, for the browser and for adb."""

import json
import shlex
import sys
import time
from pathlib import Path

import pytest

from holotouch.config import Config
from holotouch.core.actions import WindowInfo
from holotouch.launcher import phone
from holotouch.launcher.phone import NO_LINK, NO_PHONE, SENDING, SENT, PhoneLink, browser_in_front, phone_command
from holotouch.x11.fake import FakeBackend

# A clipboard kept in a directory, answering as xclip does: -o prints its text, or with
# -t TIMESTAMP when it was filled, and fails while it is empty; -i fills it from what it is given.
_XCLIP = """
import pathlib, sys
box, args = pathlib.Path(sys.argv[1]), sys.argv[2:]
text, stamp = box / "text", box / "stamp"
if "-i" in args:
    text.write_text(sys.stdin.read())
    stamp.write_text(str(int(stamp.read_text()) + 1 if stamp.exists() else 1))
else:
    wanted = stamp if "TIMESTAMP" in args else text
    if not wanted.exists():
        sys.exit(1)
    sys.stdout.write(wanted.read_text())
"""
# Notes what it was asked, then says what the file beside it tells it to and ends as that says.
_ADB = """
import json, pathlib, sys
box = pathlib.Path(sys.argv[1])
with open(box / "asked", "a") as asked:
    asked.write(json.dumps(sys.argv[2:]) + "\\n")
status, _, says = (box / "answer").read_text().partition(" ")
print(says)
sys.exit(int(status))
"""
PAGE = "https://example.com/read?a=1&b=two"


class Browser(FakeBackend):
    """A browser window has the keyboard, and Ctrl+C in it copies `address`: nothing, if that is None."""

    def __init__(self, box, address=PAGE, wm_class="Google-chrome"):
        super().__init__()
        self.box, self.address = box, address
        self.add_window(WindowInfo(1, 0, 0, 800, 600, title="a page", wm_class=wm_class))
        self.activate(1)
        self.commands.clear()

    def press_key(self, key):
        super().press_key(key)
        if key == "ctrl+c" and self.address is not None:
            fill(self.box, self.address)


def fill(box, text):
    stamp = box / "stamp"
    (box / "text").write_text(text)
    stamp.write_text(str(int(stamp.read_text()) + 1 if stamp.exists() else 1))


def held(box):
    """What the clipboard holds; None while it is empty."""
    return (box / "text").read_text() if (box / "text").exists() else None


def asked(box):
    """What adb was asked, each time it was run."""
    return [json.loads(line) for line in (box / "asked").read_text().splitlines()] if (box / "asked").exists() else []


@pytest.fixture(autouse=True)
def no_phone_found(tmp_path, monkeypatch):
    """No phone's address on the network is remembered, whatever `holotouch phone` has found on this machine."""
    monkeypatch.setattr(phone, "PHONE_PATH", tmp_path / "phone")


@pytest.fixture
def box(tmp_path, monkeypatch):
    """Where the stand-in clipboard is kept, and what adb is to answer: by default, as a phone that took the page."""
    for name, source in (("xclip.py", _XCLIP), ("adb.py", _ADB)):
        (tmp_path / name).write_text(source)
    monkeypatch.setattr(phone, "_CLIPBOARD", (sys.executable, str(tmp_path / "xclip.py"), str(tmp_path)))
    monkeypatch.setattr(phone, "_ADB", (sys.executable, str(tmp_path / "adb.py"), str(tmp_path)))
    (tmp_path / "answer").write_text("0 Starting: Intent { act=android.intent.action.VIEW }")
    monkeypatch.setattr(phone, "_FAILED_SHOWN_S", 0.05)  # the notes are not left up for anyone to read
    return tmp_path


def link_to(backend):
    cfg = Config()
    cfg.ui.hud_ms = 50.0
    return PhoneLink(cfg, backend)


def play(link, timeout=10.0):
    """Send the page and step until there is no more to say; every note said on the way."""
    began = link.send(time.monotonic())
    said, deadline = [], time.monotonic() + timeout
    while time.monotonic() < deadline:
        note = link.step(time.monotonic())
        if not said or said[-1] != note:
            said.append(note)
        if note == "":
            link.close()
            return began, said
        time.sleep(0.005)
    raise AssertionError(f"never done: {said}")


def test_the_page_in_the_browser_is_opened_on_the_phone_and_the_clipboard_put_back(box):
    fill(box, "what was copied before")
    backend = Browser(box)
    began, said = play(link_to(backend))
    assert began and said == [SENDING, SENT, ""]
    # The address bar is gone to, the address copied, and the keyboard handed back to the page.
    assert backend.commands == [("press_key", key) for key in ("ctrl+l", "ctrl+c", "Escape", "shift+F6")]
    view = f"input keyevent KEYCODE_WAKEUP; am start -a android.intent.action.VIEW -d {shlex.quote(PAGE)}"
    assert asked(box) == [["shell", view]]
    assert held(box) == "what was copied before"


def test_an_empty_clipboard_is_left_holding_the_address(box):
    began, said = play(link_to(Browser(box)))
    assert began and said == [SENDING, SENT, ""]
    assert held(box) == PAGE and len(asked(box)) == 1


def test_a_page_whose_address_was_on_the_clipboard_already_is_still_sent(box):
    fill(box, PAGE)
    began, said = play(link_to(Browser(box)))
    assert said == [SENDING, SENT, ""] and len(asked(box)) == 1
    assert held(box) == PAGE


def test_nothing_is_sent_when_the_browser_copies_nothing(box):
    fill(box, "https://example.com/copied-earlier")
    backend = Browser(box, address=None)
    began, said = play(link_to(backend))
    assert began and said == [SENDING, NO_LINK, ""]
    assert not asked(box)  # what was copied earlier is not the page, and is not sent in its place
    assert held(box) == "https://example.com/copied-earlier"
    assert backend.commands[-2:] == [("press_key", "Escape"), ("press_key", "shift+F6")]


@pytest.mark.parametrize("address", ["chrome://newtab/", "about:blank", "file:///home/me/notes.html", "two words", ""])
def test_nothing_is_sent_from_a_page_a_phone_cannot_open(box, address):
    fill(box, "before")
    began, said = play(link_to(Browser(box, address)))
    assert said == [SENDING, NO_LINK, ""] and not asked(box)
    assert held(box) == "before"


@pytest.mark.parametrize("wm_class", ["com.mitchellh.ghostty", "Thunar", ""])
def test_no_key_is_pressed_when_it_is_not_a_browser_that_has_the_keyboard(box, wm_class):
    backend = Browser(box, wm_class=wm_class)
    assert browser_in_front(backend, Config()) is None
    began, said = play(link_to(backend))
    assert not began and said == [""]
    assert not backend.commands and not asked(box)


def test_no_key_is_pressed_with_no_window_at_all(box):
    backend = FakeBackend()
    began, said = play(link_to(backend))
    assert not began and not backend.commands


@pytest.mark.parametrize(
    "answer",
    [
        "1 adb: no devices/emulators found",
        "1 adb: device unauthorized.",
        "0 Starting: Intent { act=android.intent.action.VIEW }\nError: Activity not started, unable to resolve Intent",
    ],
)
def test_a_phone_that_is_not_there_or_takes_no_page_is_said_to_be_missing(box, answer):
    (box / "answer").write_text(answer)
    fill(box, "before")
    began, said = play(link_to(Browser(box)))
    assert began and said == [SENDING, NO_PHONE, ""]
    assert held(box) == "before"


def test_a_second_page_is_not_begun_while_one_is_on_its_way(box):
    link = link_to(Browser(box))
    assert link.send(time.monotonic()) and link.busy
    assert not link.send(time.monotonic())
    began, said = play(link)
    assert not began and said == [SENDING, SENT, ""]
    assert len(asked(box)) == 1


def test_the_phone_is_told_what_the_configuration_says():
    cfg = Config()
    cfg.phone.action, cfg.phone.app, cfg.phone.serial, cfg.phone.wake = "share", "com.brave.browser", "a85a9b46", False
    assert phone_command(cfg, PAGE) == [
        "adb", "-s", "a85a9b46", "shell",
        f"am start -a android.intent.action.SEND -t text/plain --es android.intent.extra.TEXT {shlex.quote(PAGE)} -p com.brave.browser",
    ]  # fmt: skip
    cfg.phone.action = "print"
    assert phone_command(cfg, PAGE) is None


def test_an_address_cannot_run_anything_in_the_phones_shell():
    address = "https://example.com/a';reboot;'$(reboot)`reboot`"
    line = phone_command(Config(), address)[-1]
    assert shlex.split(line)[-1] == address  # one word, whatever is in it
    assert shlex.split(line)[:5] == ["input", "keyevent", "KEYCODE_WAKEUP;", "am", "start"]


WIFI = "192.168.1.23:5555"


def test_a_phone_found_on_the_network_is_sent_the_page_over_wifi(box):
    (box / "phone").write_text(WIFI + "\n")
    began, said = play(link_to(Browser(box)))
    assert began and said == [SENDING, SENT, ""]
    view = f"input keyevent KEYCODE_WAKEUP; am start -a android.intent.action.VIEW -d {shlex.quote(PAGE)}"
    # It is looked for on the network first, and then told.
    assert asked(box) == [["connect", WIFI], ["-s", WIFI, "shell", view]]


def test_a_phone_not_reached_over_wifi_is_sent_the_page_by_usb_if_it_is_plugged_in(box):
    (box / "phone").write_text(WIFI)
    # adb fails whatever it is asked, as it does for a phone that is not there.
    (box / "answer").write_text("1 adb: device '192.168.1.23:5555' not found")
    began, said = play(link_to(Browser(box)))
    assert said == [SENDING, NO_PHONE, ""]
    assert [words[:2] for words in asked(box)] == [["connect", WIFI], ["-s", WIFI], ["-d", "shell"]]


def test_the_phone_named_in_the_configuration_comes_before_the_one_found(tmp_path):
    (tmp_path / "phone").write_text(WIFI)
    cfg = Config()
    assert phone.phone_at(cfg) == WIFI
    cfg.phone.serial = "a85a9b46"
    assert phone.phone_at(cfg) == "a85a9b46"
    assert phone_command(cfg, PAGE)[:4] == ["adb", "-s", "a85a9b46", "shell"]
    cfg.phone.serial = "10.0.0.7:5555"  # one on the network, named there, is looked for too
    assert phone_command(cfg, PAGE)[:2] == ["sh", "-c"] and "connect 10.0.0.7:5555" in phone_command(cfg, PAGE)[2]


def test_an_address_cannot_run_anything_in_either_shell_on_the_way_to_a_phone_on_the_network(box):
    (box / "phone").write_text(WIFI)
    address = "https://example.com/a';touch${IFS}pwned;'$(touch${IFS}pwned)`touch${IFS}pwned`\"&x=1"  # no spaces: it is one address
    began, said = play(link_to(Browser(box, address)))
    assert said == [SENDING, SENT, ""]
    line = asked(box)[-1][-1]
    assert shlex.split(line)[-1] == address  # one word for the phone's shell, having been one for this machine's
    assert not (box / "pwned").exists() and not Path("pwned").exists()

"""The page in the web browser, sent to an Android phone: its address is read, and adb hands it over.

A browser tells no other program which page it shows, so the address is taken as a person would
take it: Ctrl+L puts the keyboard in the address bar with the address selected, Ctrl+C copies it,
and the clipboard is read. What the clipboard held is put back if it was text. The phone is then
told to open the address, over adb: by Wi-Fi once pair() has been run with the phone plugged in,
and by USB otherwise.

Nothing here waits. The clipboard is read by xclip and the phone is reached by adb, each a
separate process looked in on every tick, so a slow one cannot stall the overlay. Under Wayland
xclip cannot be relied on, and the clipboard is read through the backend instead, which asks the
compositor.
"""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import time

from holotouch.config import PHONE_PATH, Config
from holotouch.core.actions import WindowBackend, WindowInfo

log = logging.getLogger(__name__)

_CLIPBOARD = ("xclip", "-selection", "clipboard")
_ADB = ("adb",)
_FOCUS_S = 0.05  # how long the browser is given to select the address before it is told to copy it
_AGAIN_S = 0.03  # how long after that the clipboard is first read, and between one reading and the next
_COPY_S = 0.8  # how long the address has to turn up on the clipboard
_PHONE_S = 10.0  # how long adb has to reach the phone
_CONNECT_S = 3  # how long of that it may spend looking for the phone on the network
_PORT = 5555  # where the phone listens for adb on the network
_ALLOW_S = 60.0  # how long pair() waits for debugging over Wi-Fi to be allowed on the phone
_FAILED_SHOWN_S = 2.0  # how long the overlay says that the page could not be sent
_ADDRESS = re.compile(r"https?://\S+")  # what a phone can open: not about:blank, chrome://newtab or a file

SENDING, SENT, NO_LINK, NO_PHONE = "Sending to phone", "Sent to phone", "No link to send", "No phone connected"


def browser_in_front(backend: WindowBackend, cfg: Config) -> WindowInfo | None:
    """The window that has the keyboard, if it is a web browser's: one of [gesture] clap_browsers."""
    win = backend.active_window()
    words = set(re.findall(r"[a-z0-9]+", win.wm_class.lower())) if win is not None else set()
    return win if words & set(cfg.gesture.clap_browsers.lower().replace(",", " ").split()) else None


def phone_at(cfg: Config) -> str:
    """Which phone a page goes to: [phone] serial, or the address pair() found; empty for whichever is plugged in."""
    if cfg.phone.serial:
        return cfg.phone.serial
    try:
        return PHONE_PATH.read_text().strip()
    except OSError:
        return ""


def phone_command(cfg: Config, address: str) -> list[str] | None:
    """The command that hands the phone an address; None if [phone] action names nothing known."""
    p = cfg.phone
    if p.action == "view":
        start = f"am start -a android.intent.action.VIEW -d {shlex.quote(address)}"
    elif p.action == "share":
        start = f"am start -a android.intent.action.SEND -t text/plain --es android.intent.extra.TEXT {shlex.quote(address)}"
    else:
        return None
    if p.app:
        start += f" -p {shlex.quote(p.app)}"
    # The phone's shell runs this as one line, which is why the address is quoted for it.
    wake = "input keyevent KEYCODE_WAKEUP; " if p.wake else ""
    line, at = wake + start, phone_at(cfg)
    if ":" not in at:
        return [*_ADB, *(["-s", at] if at else []), "shell", line]
    # A phone on the network. adb forgets it whenever either end has been away, so it is looked
    # for afresh each time, which costs nothing while it is still known. Where it cannot be
    # reached that way, the phone that is plugged in is sent the page instead.
    adb, line = shlex.join(_ADB), shlex.quote(line)
    return [
        "sh", "-c",
        f"timeout {_CONNECT_S} {adb} connect {shlex.quote(at)} >/dev/null 2>&1; "
        f"{adb} -s {shlex.quote(at)} shell {line} || {adb} -d shell {line}",
    ]  # fmt: skip


def _adb(*args: str, timeout: float = 15.0) -> tuple[bool, str]:
    """Run adb and wait for it: whether it ended well, and what it said."""
    try:
        done = subprocess.run([*_ADB, *args], capture_output=True, text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "adb did not answer"
    except OSError as exc:
        return False, f"adb is needed ({exc.strerror or exc})"
    return done.returncode == 0, (done.stdout + done.stderr).strip()


def pair(cfg: Config, say=print) -> bool:
    """Let the phone that is plugged in be reached over Wi-Fi from now on. This waits, and is not for the overlay.

    The phone is asked where it is on the network and told to listen for adb there, and its
    address is kept in PHONE_PATH. It listens until it is next restarted; run again then, and
    whenever the network has given it another address.
    """
    usb = ("-s", cfg.phone.serial) if cfg.phone.serial and ":" not in cfg.phone.serial else ("-d",)
    good, said = _adb(*usb, "shell", "ip -f inet -o addr show wlan0")
    found = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", said)
    if not good or found is None:
        say("no phone is plugged in with USB debugging allowed" if not good else "the phone is not on Wi-Fi")
        if not good and said:
            say(f"  ({said.splitlines()[-1]})")
        return False
    at = f"{found.group(1)}:{_PORT}"
    good, said = _adb(*usb, "tcpip", str(_PORT))
    if not good:
        say(f"the phone would not listen on the network: {said}")
        return False
    time.sleep(2.0)  # the phone's adb starts again, and is not there for a moment
    deadline, asked = time.monotonic() + _ALLOW_S, False
    while time.monotonic() < deadline:
        _adb("connect", at, timeout=_CONNECT_S + 2)
        state = _adb("-s", at, "get-state", timeout=5.0)[1]
        if state == "device":
            PHONE_PATH.parent.mkdir(parents=True, exist_ok=True)
            PHONE_PATH.write_text(at + "\n")
            say(f"the phone is reached over Wi-Fi at {at}: the cable can come out")
            return True
        if "unauthorized" in state and not asked:
            say('the phone is asking whether to allow debugging: tick "Always allow from this computer" and allow it')
            asked = True
        time.sleep(1.0)
    say(f"the phone could not be reached at {at}: is this computer on the same network, and does the network let them talk?")
    return False


def unpair(cfg: Config, say=print) -> None:
    """Forget the phone's address on the network, and have it listen for adb by USB alone again."""
    at = phone_at(cfg)
    PHONE_PATH.unlink(missing_ok=True)
    if ":" in at:
        _adb("-s", at, "usb", timeout=5.0)
        _adb("disconnect", at, timeout=5.0)
    say("the phone is reached by USB alone")



class PhoneLink:
    """Call send() when the page is to go to the phone, and step() every tick."""

    def __init__(self, cfg: Config, backend: WindowBackend):
        self.cfg = cfg
        self.backend = backend
        self._stage = ""  # "saving" what the clipboard holds, "copying" the address, "reading" it, "sending" it
        self._due = 0.0  # when the next step of it may be taken
        self._deadline = 0.0  # when the stage it is at is given up
        self._readers: list[subprocess.Popen] = []  # xclip, printing the clipboard's text and when it was filled
        # A backend that can read the clipboard itself, which is then not xclip's to read.
        self._direct = getattr(backend, "clipboard", None)
        self._read_direct: tuple[str | None, str | None] | None = None  # what it read, until collected
        self._held: tuple[str | None, str | None] = (None, None)  # what they printed before the address was copied
        self._reread = False  # the clipboard was seen to be newer, and its text has been read again since
        self._adb: subprocess.Popen | None = None
        self._strays: list[subprocess.Popen] = []  # processes that are done with, until they have ended
        self._note, self._note_until = "", 0.0

    @property
    def busy(self) -> bool:
        return bool(self._stage)

    def send(self, now: float) -> bool:
        """Begin sending the page of the browser that has the keyboard; False if there is none, or one is on its way."""
        if self.busy:
            return False
        if browser_in_front(self.backend, self.cfg) is None:
            # The keys below would be typed into whatever does have the keyboard.
            log.info("nothing sent to the phone: it is no web browser that has the keyboard")
            return False
        if not self._read():
            self._fail(now, NO_LINK, "cannot read the clipboard: xclip is needed")
            return False
        self._stage, self._deadline, self._reread = "saving", now + _COPY_S, False
        return True

    def step(self, now: float) -> str:
        """What the overlay should say: that the page is being sent, has been, could not be, or nothing."""
        self._strays = [process for process in self._strays if process.poll() is None]
        if self._stage == "saving":
            held = self._collect(now)
            if held is not None:
                self._held = held
                self.backend.press_key("ctrl+l")
                self._stage, self._due = "copying", now + _FOCUS_S
        elif self._stage == "copying" and now >= self._due:
            self.backend.press_key("ctrl+c")
            self._stage, self._due, self._deadline = "reading", now + _AGAIN_S, now + _COPY_S
        elif self._stage == "reading":
            self._step_reading(now)
        elif self._stage == "sending":
            self._step_sending(now)
        if self._stage:
            return SENDING
        return self._note if now < self._note_until else ""

    # -- the address -------------------------------------------------------------------------

    def _read(self) -> bool:
        """Start reading the clipboard: its text, and the time its owner took it, which tells a new copy from the last."""
        if self._direct is not None:
            self._read_direct = self._direct()
            return True
        try:
            self._readers = [
                subprocess.Popen(
                    [*_CLIPBOARD, "-o", *target], text=True, errors="replace",
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                )
                for target in ((), ("-t", "TIMESTAMP"))
            ]  # fmt: skip
        except OSError:
            self._drop_readers()
            return False
        return True

    def _collect(self, now: float) -> tuple[str | None, str | None] | None:
        """What the readers printed, each None if it could print nothing; None while they are still at it."""
        if self._read_direct is not None:
            read, self._read_direct = self._read_direct, None
            return read
        if not self._readers:
            return None
        if any(reader.poll() is None for reader in self._readers):
            if now < self._deadline:
                return None
            # An owner that does not answer: xclip would wait on it for ever.
            for reader in self._readers:
                reader.kill()
        printed = []
        for reader in self._readers:
            output = reader.stdout.read() if reader.wait() == 0 else None
            reader.stdout.close()
            printed.append(output)
        self._readers = []
        return printed[0], printed[1]

    def _drop_readers(self) -> None:
        for reader in self._readers:
            if reader.poll() is None:
                reader.kill()
            reader.wait()
            reader.stdout.close()
        self._readers = []

    def _step_reading(self, now: float) -> None:
        if not self._readers and self._read_direct is None:
            if now >= self._due and not self._read():
                self._fail(now, NO_LINK, "cannot read the clipboard: xclip is needed")
            return
        read = self._collect(now)
        if read is None:
            return
        (text, stamp), (old_text, old_stamp) = read, self._held
        # The browser has copied once the clipboard is newer than it was, or says something else.
        copied = text is not None and ((stamp is not None and stamp != old_stamp) or text != old_text)
        if not copied and now < self._deadline:
            self._due = now + _AGAIN_S
            return
        if copied and text == old_text and not self._reread:
            # The two are read side by side, so the text may have been read just before the copy
            # and the time just after it. Read once more, the text is what was copied.
            self._reread, self._due = True, now
            return
        # The keyboard goes back to the page: Escape shuts the list under the address bar, and
        # Shift+F6 steps from the bar to the pane before it, which is the page.
        self.backend.press_key("Escape")
        self.backend.press_key("shift+F6")
        if copied and old_text is not None and old_text != text:
            self._write(old_text)
        if not copied:
            self._fail(now, NO_LINK, "the browser copied no address")
            return
        address = text.strip()
        if not _ADDRESS.fullmatch(address):
            self._fail(now, NO_LINK, "the page has no address a phone can open")
            return
        self._phone(address, now)

    def _write(self, text: str) -> None:
        """Put text on the clipboard. xclip stays behind to hand it out, until something else is copied."""
        if self._direct is not None:
            self.backend.set_clipboard(text)
            return
        try:
            writer = subprocess.Popen(
                [*_CLIPBOARD, "-i"], text=True, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            writer.stdin.write(text)
            writer.stdin.close()
        except OSError as exc:
            log.warning("could not put back what the clipboard held: %s", exc)
            return
        self._strays.append(writer)

    # -- the phone ---------------------------------------------------------------------------

    def _phone(self, address: str, now: float) -> None:
        command = phone_command(self.cfg, address)
        if command is None:
            self._fail(now, NO_PHONE, '[phone] action is %r: it has to be "view" or "share"', self.cfg.phone.action)
            return
        try:
            self._adb = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        except OSError as exc:
            self._fail(now, NO_PHONE, "cannot reach the phone: adb is needed (%s)", exc.strerror or exc)
            return
        log.info("sending the page to the phone")  # which page is nobody's business but the phone's
        self._stage, self._deadline = "sending", now + _PHONE_S

    def _step_sending(self, now: float) -> None:
        adb = self._adb
        if adb.poll() is None:
            if now < self._deadline:
                return
            adb.kill()
        adb.wait()
        # Only what it has said by now is read: an adb that had to start its server leaves that
        # behind, and the server may hold on to the pipe.
        os.set_blocking(adb.stdout.fileno(), False)
        said = (adb.stdout.read() or b"").decode(errors="replace").strip()
        adb.stdout.close()
        self._adb = None
        # `am start` ends well even when nothing on the phone takes the address, and says so.
        if adb.returncode != 0 or "Error" in said:
            self._fail(now, NO_PHONE, "the phone was not sent the page: %s", said.splitlines()[-1] if said else "it did not answer")
            return
        self._stage = ""
        self._note, self._note_until = SENT, now + self.cfg.ui.hud_ms / 1000.0

    def _fail(self, now: float, note: str, why: str, *args) -> None:
        log.warning(why, *args)
        self._stage = ""
        self._note, self._note_until = note, now + _FAILED_SHOWN_S

    def close(self) -> None:
        """Stop at once: a page on its way is not sent."""
        self._drop_readers()
        self._read_direct = None
        if self._adb is not None:
            if self._adb.poll() is None:
                self._adb.kill()
            self._adb.wait()
            self._adb.stdout.close()
            self._adb = None
        # What the clipboard held is still put back: xclip has only to take it, which is quick.
        for writer in self._strays:
            try:
                writer.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                writer.kill()
                writer.wait()
        self._strays.clear()
        self._stage = ""

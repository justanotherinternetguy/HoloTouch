"""The line to HoloTouch's GNOME Shell extension: method calls over the session bus, and its signals."""

from __future__ import annotations

import logging
import time

from jeepney import DBusAddress, HeaderFields, MatchRule, MessageType, message_bus, new_method_call
from jeepney.io.blocking import open_dbus_connection
from jeepney.low_level import MessageFlag

log = logging.getLogger(__name__)

BUS_NAME = "dev.internetguy.HoloTouch"
OBJECT_PATH = "/dev/internetguy/HoloTouch"
_SETUP_S = 2.0  # how long the bus has to answer while the line is being set up


class ShellLink:
    """Nothing here waits unless asked to: a call is sent and forgotten, or its answer is handed
    over by poll() when it comes, so a compositor that is busy cannot stall the overlay."""

    def __init__(self):
        self._conn = open_dbus_connection(bus="SESSION")
        self._address = DBusAddress(OBJECT_PATH, bus_name=BUS_NAME, interface=BUS_NAME)
        self._waiting: dict[int, object] = {}  # serial of a call -> what to do with its answer
        self._signals: list[tuple[str, tuple]] = []  # read while waiting for something else
        self._broken = False
        rule = MatchRule(type="signal", interface=BUS_NAME, path=OBJECT_PATH)
        self._conn.send_and_get_reply(message_bus.AddMatch(rule), timeout=_SETUP_S)

    def _send(self, member: str, signature: str, args: tuple, reply: bool) -> int | None:
        message = new_method_call(self._address, member, signature or None, args or None)
        if not reply:
            message.header.flags |= MessageFlag.no_reply_expected
        serial = next(self._conn.outgoing_serial)
        try:
            self._conn.send(message, serial=serial)
        except OSError as exc:
            if not self._broken:
                log.error("the session bus is gone: %s", exc)
            self._broken = True
            return None
        return serial

    def _receive(self, timeout: float):
        try:
            return self._conn.receive(timeout=timeout)
        except TimeoutError:
            return None
        except (OSError, EOFError) as exc:  # the bus has hung up
            if not self._broken:
                log.error("the session bus is gone: %s", exc)
            self._broken = True
            return None

    def _sort(self, message, wanted: int | None = None) -> tuple | None:
        """Put a message where it belongs. The body of the answer to call `wanted`, if this is it."""
        header = message.header
        if header.message_type is MessageType.signal:
            self._signals.append((header.fields.get(HeaderFields.member, ""), message.body))
            return None
        serial = header.fields.get(HeaderFields.reply_serial)
        good = header.message_type is MessageType.method_return
        if not good and header.message_type is MessageType.error:
            log.debug("GNOME Shell: %s", header.fields.get(HeaderFields.error_name))
        if serial == wanted:
            return message.body if good else ()
        then = self._waiting.pop(serial, None)
        if then is not None and good:
            then(*message.body)
        return None

    def send(self, member: str, signature: str = "", *args) -> None:
        """Call a method and do not wait for it."""
        self._send(member, signature, args, reply=False)

    def ask(self, member: str, signature: str = "", *args, timeout: float = 1.0) -> tuple | None:
        """Call a method and wait for what it returns; None if it failed or did not answer in time."""
        serial = self._send(member, signature, args, reply=True)
        if serial is None:
            return None
        deadline = time.monotonic() + timeout
        while (message := self._receive(max(deadline - time.monotonic(), 0.0))) is not None:
            body = self._sort(message, serial)
            if body is not None:
                return body or None  # an error answers with nothing
        return None

    def ask_later(self, member: str, then, signature: str = "", *args) -> None:
        """Call a method; poll() hands what it returns to `then` once it has, if it ever does."""
        serial = self._send(member, signature, args, reply=True)
        if serial is not None:
            if len(self._waiting) > 64:  # answers that never came
                self._waiting.clear()
            self._waiting[serial] = then

    def poll(self) -> list[tuple[str, tuple]]:
        """Everything that has arrived, without waiting: the signals, each by its name and what it carries."""
        while not self._broken and (message := self._receive(0)) is not None:
            self._sort(message)
        signals, self._signals = self._signals, []
        return signals

    def close(self) -> None:
        self._conn.close()

"""Thin xcffib wrapper: atoms, property reads, EWMH client messages and server timestamps."""

from __future__ import annotations

import struct

import xcffib
import xcffib.xproto as xp

_ROOT_MESSAGE_MASK = xp.EventMask.SubstructureRedirect | xp.EventMask.SubstructureNotify


class X11:
    def __init__(self, display: str | None = None):
        self.conn = xcffib.connect(display) if display else xcffib.connect()
        self.core = self.conn.core
        self.screen = self.conn.get_setup().roots[self.conn.pref_screen]
        self.root = self.screen.root
        self._atoms: dict[str, int] = {}
        self.pending: list = []  # events read while waiting for something else
        # A private window whose property changes give us current server timestamps.
        self._helper = self.conn.generate_id()
        self.core.CreateWindow(
            0, self._helper, self.root, -10, -10, 1, 1, 0, xp.WindowClass.InputOnly, 0,
            xp.CW.EventMask, [xp.EventMask.PropertyChange],
        )
        self.conn.flush()

    def atom(self, name: str) -> int:
        atom = self._atoms.get(name)
        if atom is None:
            atom = self.core.InternAtom(False, len(name), name).reply().atom
            self._atoms[name] = atom
        return atom

    def reply(self, cookie):
        """The reply, or None if the request failed (typically the window no longer exists)."""
        try:
            return cookie.reply()
        except xcffib.Error:
            return None

    def get_property(self, window: int, name: str):
        return self.core.GetProperty(False, window, self.atom(name), xp.GetPropertyType.Any, 0, 4096)

    @staticmethod
    def cardinals(reply) -> list[int]:
        if reply is None or reply.format != 32 or reply.value_len == 0:
            return []
        return list(struct.unpack_from(f"{reply.value_len}I", reply.value.buf()))

    @staticmethod
    def text(reply) -> str:
        if reply is None or reply.format != 8:
            return ""
        return reply.value.buf().decode("utf-8", errors="replace")

    def send_root_message(self, window: int, message: str, data: list[int]) -> None:
        """Send an EWMH request about `window` to the window manager."""
        values = [v & 0xFFFFFFFF for v in data] + [0] * (5 - len(data))
        event = struct.pack("BBHII5I", 33, 32, 0, window, self.atom(message), *values)
        self.core.SendEvent(False, self.root, _ROOT_MESSAGE_MASK, event)

    def timestamp(self) -> int:
        """A fresh server timestamp, which the window manager needs to honour focus requests."""
        atom = self.atom("_HOLOWM_TIME")
        self.core.ChangeProperty(xp.PropMode.Append, self._helper, atom, xp.Atom.STRING, 8, 0, b"")
        self.conn.flush()
        while True:
            try:
                event = self.conn.wait_for_event()
            except xcffib.Error:
                continue
            if isinstance(event, xp.PropertyNotifyEvent) and event.window == self._helper:
                return event.time
            self.pending.append(event)

    def events(self):
        """All events that have arrived, without blocking."""
        pending, self.pending = self.pending, []
        yield from pending
        while True:
            try:
                event = self.conn.poll_for_event()
            except xcffib.Error:
                continue  # an asynchronous error, e.g. a request for a window that just closed
            if event is None:
                return
            yield event

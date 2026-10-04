"""Input injection: wheel events from a uinput virtual mouse or XTEST, and XTEST clicks and key presses."""

from __future__ import annotations

import logging

import xcffib.xtest

from holotouch.x11.conn import X11

log = logging.getLogger(__name__)

_KEY_PRESS, _KEY_RELEASE = 2, 3
_BUTTON_PRESS, _BUTTON_RELEASE = 4, 5
_NAMED_KEYS = {"space": 0x20, "Return": 0xFF0D, "Escape": 0xFF1B}  # X keysyms; a Latin-1 character is its own
_MODIFIERS = {"ctrl": 0xFFE3, "shift": 0xFFE1, "alt": 0xFFE9}  # the left one of each
_WHEEL_UP, _WHEEL_DOWN = 4, 5
_HI_RES_PER_NOTCH = 120


class XTestScroller:
    """Whole wheel notches through the XTEST extension. Works everywhere, but steps are coarse."""

    def __init__(self, x: X11):
        self._x = x
        self._xtest = x.conn(xcffib.xtest.key)
        self._acc = 0.0

    def scroll(self, notches: float) -> None:
        self._acc += notches
        while abs(self._acc) >= 1.0:
            button = _WHEEL_UP if self._acc > 0 else _WHEEL_DOWN
            self._xtest.FakeInput(_BUTTON_PRESS, button, 0, self._x.root, 0, 0, 0)
            self._xtest.FakeInput(_BUTTON_RELEASE, button, 0, self._x.root, 0, 0, 0)
            self._acc -= 1.0 if self._acc > 0 else -1.0

    def close(self) -> None:
        pass


class UinputScroller:
    """A virtual mouse that emits hi-res wheel events (1/120 notch), so scrolling is smooth."""

    def __init__(self):
        from evdev import UInput, ecodes as e

        self._e = e
        capabilities = {
            e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL, e.REL_WHEEL_HI_RES],
            e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE],
        }
        self._device = UInput(capabilities, name="HoloTouch virtual scroll")
        self._hi_res = 0.0
        self._detent = 0

    def scroll(self, notches: float) -> None:
        e = self._e
        self._hi_res += notches * _HI_RES_PER_NOTCH
        units = int(self._hi_res)
        if units == 0:
            return
        self._hi_res -= units
        self._device.write(e.EV_REL, e.REL_WHEEL_HI_RES, units)
        self._detent += units
        whole = int(self._detent / _HI_RES_PER_NOTCH)
        if whole:
            self._detent -= whole * _HI_RES_PER_NOTCH
            self._device.write(e.EV_REL, e.REL_WHEEL, whole)
        self._device.syn()

    def close(self) -> None:
        self._device.close()


def press_button(x: X11, down: bool, button: int = 1) -> None:
    """Press a mouse button where the pointer is, or let it go."""
    x.conn(xcffib.xtest.key).FakeInput(_BUTTON_PRESS if down else _BUTTON_RELEASE, button, 0, x.root, 0, 0, 0)


def press_key(x: X11, key: str) -> bool:
    """Press and release the key that types `key` unshifted, in whichever window has the keyboard.

    "ctrl+t" is t with Control held; shift and alt are held the same way. False if the keyboard
    has no such key, and then nothing is pressed.
    """
    *held, key = key.split("+") if len(key) > 1 else [key]
    keysyms = [_MODIFIERS.get(name) for name in held] + [_NAMED_KEYS.get(key) or (ord(key) if len(key) == 1 else None)]
    setup = x.conn.get_setup()
    first, count = setup.min_keycode, setup.max_keycode - setup.min_keycode + 1
    mapping = x.core.GetKeyboardMapping(first, count).reply()
    unshifted = [mapping.keysyms[index * mapping.keysyms_per_keycode] for index in range(count)]
    if any(keysym is None or keysym not in unshifted for keysym in keysyms):
        return False
    keycodes = [first + unshifted.index(keysym) for keysym in keysyms]
    xtest = x.conn(xcffib.xtest.key)
    for keycode in keycodes:
        xtest.FakeInput(_KEY_PRESS, keycode, 0, x.root, 0, 0, 0)
    for keycode in reversed(keycodes):
        xtest.FakeInput(_KEY_RELEASE, keycode, 0, x.root, 0, 0, 0)
    x.conn.flush()
    return True


def make_scroller(mode: str, x: X11):
    if mode in ("auto", "uinput"):
        try:
            return UinputScroller()
        except Exception as exc:  # no /dev/uinput access, or evdev missing
            if mode == "uinput":
                raise
            log.info("uinput unavailable (%s); scrolling with XTEST", exc)
    return XTestScroller(x)

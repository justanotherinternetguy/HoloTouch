"""What the launcher opens: macros, each a few letters of the manual alphabet and what they set off, and the installed apps."""

from __future__ import annotations

import logging
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from holowm.config import MACROS_PATH
from holowm.core.actions import WindowBackend
from holowm.core.letters import LETTERS

log = logging.getLogger(__name__)

MACRO_TYPES = (
    "url",  # data: an address, opened in the web browser
    "command",  # data: shell command
    "app",  # data: desktop file id
    "key",  # data: a key pressed in whatever has the keyboard, as "ctrl+t"
    "text",  # data: text typed into whatever has the keyboard
)


@dataclass(frozen=True)
class Macro:
    letters: str  # what is spelt to run it, in lower case
    name: str  # what the overlay calls it
    type: str = "command"
    data: str = ""
    icon: str = ""  # an icon's name in the theme, or the path of a picture; apps have one
    # An installed app (see apps.py): its letters are its name, and it is opened as soon as what
    # has been spelt can be nothing else. A macro has to be spelt in full.
    by_name: bool = False


def macro_from_dict(d: dict) -> Macro:
    letters = str(d.get("letters", "")).lower()
    name = str(d.get("name", letters.upper()))
    if not letters:
        raise ValueError(f"macro {name!r} has no letters to spell it with")
    unread = sorted(set(letters) - set(LETTERS))
    if unread:
        why = "J and Z are drawn in the air, which is not read" if set(unread) <= {"j", "z"} else "only letters can be spelt"
        raise ValueError(f"macro {name!r}: {', '.join(unread).upper()} cannot be spelt ({why})")
    macro_type = d.get("type", "command")
    if macro_type not in MACRO_TYPES:
        raise ValueError(f"unknown macro type {macro_type!r} for {name!r}")
    if not str(d.get("data", "")):
        raise ValueError(f"macro {name!r} has no data: what its {macro_type} is")
    return Macro(letters, name, macro_type, str(d["data"]))


def default_macros() -> list[Macro]:
    return [Macro("rs", "Instagram Reels", "url", "https://www.instagram.com/reels/")]


def load_macros(path: Path = MACROS_PATH) -> list[Macro]:
    if not path.exists():
        return default_macros()
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    macros = [macro_from_dict(d) for d in data.get("macro", [])]
    for index, macro in enumerate(macros):
        if any(other.letters == macro.letters for other in macros[:index]):
            raise ValueError(f"two macros are spelt {macro.letters.upper()}")
    return macros


class Macros:
    """Everything that can be spelt: the macros, and after them the apps."""

    def __init__(self, backend: WindowBackend, macros: list[Macro] | None = None, apps: list[Macro] = ()):
        self.backend = backend
        self.macros = load_macros() if macros is None else macros
        # Of two things spelt alike only the first could ever be opened, so the other is left out.
        taken = {macro.letters for macro in self.macros}
        self.apps = [app for app in apps if app.letters not in taken and not taken.add(app.letters)]
        self._all = [*self.macros, *self.apps]

    def __bool__(self) -> bool:
        return bool(self._all)

    def exact(self, spelt: str) -> Macro | None:
        """The macro or app spelt by just these letters."""
        return next((macro for macro in self._all if macro.letters == spelt), None)

    def toward(self, spelt: str) -> list[Macro]:
        """The macros and apps these letters are the start of, or the whole of."""
        return [macro for macro in self._all if macro.letters.startswith(spelt)]

    def chosen(self, spelt: str) -> Macro | None:
        """What these letters open as they stand: what they spell in full, or the one app left that they begin."""
        exact = self.exact(spelt)
        if exact is not None or not spelt:
            return exact
        toward = self.toward(spelt)
        return toward[0] if len(toward) == 1 and toward[0].by_name else None

    def next_letters(self, spelt: str) -> set[str]:
        """The letters that would carry on from these toward some macro or app."""
        return {macro.letters[len(spelt)] for macro in self.toward(spelt) if len(macro.letters) > len(spelt)}

    def run(self, macro: Macro) -> None:
        log.info("macro %s: %s", macro.letters.upper(), macro.name)
        if macro.type == "url":
            self._spawn(["xdg-open", macro.data], shell=False)
        elif macro.type == "command":
            self._spawn(macro.data, shell=True)
        elif macro.type == "app":
            self._spawn(["gtk-launch", macro.data], shell=False)
        elif macro.type == "key":
            self.backend.press_key(macro.data)
        elif macro.type == "text":
            self.backend.type_text(macro.data)

    @staticmethod
    def _spawn(command, shell: bool) -> None:
        try:
            subprocess.Popen(
                command,
                shell=shell,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            log.error("could not launch %r: %s", command, exc)

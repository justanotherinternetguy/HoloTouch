"""The apps installed on this machine, which the launcher opens when their names are spelt."""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import unicodedata
from pathlib import Path

from holowm.core.letters import LETTERS
from holowm.launcher.macros import Macro

log = logging.getLogger(__name__)

# J and Z are drawn in the air, which is not read. In a name, each is spelt by the hand that draws it.
_DRAWN = str.maketrans("jz", "id")


def spelling(name: str) -> str:
    """The letters that spell a name: its spaces, digits and accents left out, in lower case."""
    plain = unicodedata.normalize("NFKD", name).lower().translate(_DRAWN)
    return "".join(char for char in plain if char in LETTERS)


def covered(name: str, count: int) -> int:
    """How many characters of a name its first count letters take up."""
    letters = 0
    for index, char in enumerate(name):
        if letters >= count:
            return index
        letters += len(spelling(char))
    return len(name)


def app_dirs() -> list[Path]:
    """Where desktop files are looked for, the directories that count for most first."""
    home = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    system = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    dirs = [Path(home), *(Path(d) for d in system.split(":") if d)]
    return list(dict.fromkeys(d / "applications" for d in dirs))


def _entry(path: Path) -> dict[str, str]:
    """The keys of a desktop file's [Desktop Entry] group."""
    keys: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return keys
    inside = False
    for line in lines:
        line = line.strip()
        if line.startswith("["):
            if inside:
                break
            inside = line == "[Desktop Entry]"
        elif inside and "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            keys[key.strip()] = value.strip()
    return keys


def _listed(value: str) -> set[str]:
    return {item for item in value.split(";") if item}


def _installed(command: str) -> bool:
    """Whether the program an Exec line names is there to be run."""
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    return bool(words) and shutil.which(words[0]) is not None


def _shown(keys: dict[str, str], desktops: set[str]) -> bool:
    """Whether an applications menu on this desktop would list the entry, and could open it."""
    if keys.get("Type") != "Application" or not keys.get("Name"):
        return False
    if keys.get("NoDisplay") == "true" or keys.get("Hidden") == "true":
        return False
    only = _listed(keys.get("OnlyShowIn", ""))
    if (only and not only & desktops) or _listed(keys.get("NotShowIn", "")) & desktops:
        return False
    return _installed(keys.get("Exec", "")) and (not keys.get("TryExec") or shutil.which(keys["TryExec"]) is not None)


def installed_apps(dirs: list[Path] | None = None) -> list[Macro]:
    """Every app the applications menu would list, by name: each is spelt by its name, and opened by its desktop file id."""
    desktops = _listed(os.environ.get("XDG_CURRENT_DESKTOP", "").replace(":", ";"))
    apps, seen = [], set()
    for directory in app_dirs() if dirs is None else dirs:
        try:
            paths = sorted(directory.rglob("*.desktop")) if directory.is_dir() else []
        except OSError as exc:
            log.debug("could not look for apps in %s: %s", directory, exc)
            continue
        for path in paths:
            app_id = "-".join(path.relative_to(directory).parts)
            if app_id in seen:
                continue  # a file of the same name in an earlier directory stands in for this one, even to hide it
            seen.add(app_id)
            keys = _entry(path)
            if not _shown(keys, desktops):
                continue
            # A name with no letter in it that can be spelt is spelt as its file is named.
            letters = spelling(keys["Name"]) or spelling(path.stem)
            if letters:
                apps.append(Macro(letters, keys["Name"], "app", app_id, keys.get("Icon", ""), by_name=True))
    return sorted(apps, key=lambda app: (app.name.casefold(), app.data))

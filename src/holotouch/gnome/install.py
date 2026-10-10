"""`holotouch gnome`: puts HoloTouch's extension into GNOME Shell, or takes it out again."""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

UUID = "holotouch@internetguy.dev"
SOURCE = Path(__file__).parent / "extension"
_ENABLED = ("org.gnome.shell", "enabled-extensions")
_DISABLED = ("org.gnome.shell", "disabled-extensions")


def extension_dir() -> Path:
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return data_home / "gnome-shell" / "extensions" / UUID


def _run(*command: str) -> tuple[bool, str]:
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    return done.returncode == 0, done.stdout.strip()


def _listed(key: tuple[str, str]) -> list[str] | None:
    """A list of extensions out of GNOME's settings; None if it cannot be read."""
    good, said = _run("gsettings", "get", *key)
    try:
        return list(ast.literal_eval(said.removeprefix("@as ").strip())) if good else None
    except (ValueError, SyntaxError):
        return None


def _list(key: tuple[str, str], names: list[str]) -> bool:
    return _run("gsettings", "set", *key, str(names))[0]


def enabled() -> bool:
    return UUID in (_listed(_ENABLED) or []) and UUID not in (_listed(_DISABLED) or [])


def installed_version() -> int | None:
    """The version of the extension that is installed; None if none is."""
    try:
        return int(json.loads((extension_dir() / "metadata.json").read_text())["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def shell_version() -> int | None:
    """The GNOME Shell installed here, by its first number; None if it cannot be told."""
    good, said = _run("gnome-shell", "--version")  # "GNOME Shell 51.0"
    found = re.search(r"\d+", said) if good else None
    return int(found.group()) if found else None


def made_for() -> list[int]:
    """The GNOME Shell versions the extension names as its own: GNOME Shell runs it on no other."""
    return [int(v) for v in json.loads((SOURCE / "metadata.json").read_text())["shell-version"]]


def too_new() -> int | None:
    """The GNOME Shell here, if it is one the extension does not name; None if it is named, or cannot be told."""
    version = shell_version()
    return version if version is not None and version not in made_for() else None


def running_version() -> int | None:
    """The version of the extension that GNOME Shell is running now; None if it runs none."""
    from holotouch.gnome.shell import ShellLink

    try:
        link = ShellLink()
    except Exception:  # no session bus
        return None
    try:
        answer = link.ask("Watch")
        link.send("Unwatch")
        return int(json.loads(answer[0])["version"]) if answer else None
    except (ValueError, KeyError, TypeError):
        return None
    finally:
        link.close()


def install(say=print) -> bool:
    """Copy the extension to where GNOME Shell looks for it and have it turned on. True if it is running already."""
    from holotouch.gnome.backend import VERSION

    target = extension_dir()
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, target)
    say(f"installed the extension in {target}")
    # GNOME Shell turns on every extension in this list that it finds when it starts.
    names, off = _listed(_ENABLED), _listed(_DISABLED) or []
    if names is None:
        say(f"could not read GNOME's settings: turn the extension on yourself, with `gnome-extensions enable {UUID}` once you have logged in again")
    elif (UUID in names or _list(_ENABLED, [*names, UUID])) and (UUID not in off or _list(_DISABLED, [n for n in off if n != UUID])):
        say("turned it on")
    else:
        say(f"could not turn it on: do so yourself, with `gnome-extensions enable {UUID}` once you have logged in again")
    if _run("gsettings", "get", "org.gnome.shell", "disable-user-extensions") == (True, "true"):
        say("extensions are switched off as a whole: switch them on in the Extensions app, or GNOME Shell will not run this one")
    if running_version() == VERSION:
        say("GNOME Shell is running it: HoloTouch is ready")
        return True
    if (newer := too_new()) is not None:
        say(f"GNOME Shell {newer} is newer than any the extension is made for (up to {max(made_for())}), so GNOME Shell will not run it: a newer HoloTouch is needed")
        return False
    say("now log out and back in: GNOME Shell only finds a new extension, or a new version of one, when it starts")
    return False


def uninstall(say=print) -> None:
    names = _listed(_ENABLED)
    if names is not None and UUID in names:
        _list(_ENABLED, [name for name in names if name != UUID])
    target = extension_dir()
    if target.exists():
        shutil.rmtree(target)
        say(f"removed the extension from {target}; GNOME Shell runs it until you log out")
    else:
        say("the extension is not installed")

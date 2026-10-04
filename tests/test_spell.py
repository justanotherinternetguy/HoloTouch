"""Spelling: the sign that opens the launcher, the letters read, and the macro they run or the app they open."""

from pathlib import Path

import numpy as np
import pytest

from holotouch.config import Config, PoseConfig
from holotouch.core.actions import WindowInfo
from holotouch.core.engine import Engine
from holotouch.core.interactions import SpellInteraction
from holotouch.core.letters import LETTERS
from holotouch.core.overlay_state import OverlayState
from holotouch.core.poses import Pose, PoseTracker, extract_features
from holotouch.launcher.apps import covered, installed_apps, spelling as letters_of
from holotouch.launcher.macros import Macro, Macros, load_macros, macro_from_dict
from holotouch.overlay.bridge import Bridge
from holotouch.tools.score import score
from holotouch.x11.fake import FakeBackend
from synth import Sim, make_hand
from test_score import session

REPO = Path(__file__).parent.parent
SCREEN = (2880, 1800)
CENTRE = (900, 700)
REELS = Macro("rs", "Instagram Reels", "url", "https://www.instagram.com/reels/")


def app(name, app_id="", icon=""):
    return Macro(letters_of(name), name, "app", app_id or f"{letters_of(name)}.desktop", icon, by_name=True)


FIREFOX, FILES, ROLLER = app("Firefox", icon="firefox"), app("Files"), app("File Roller")


class Reads:
    """Stands in for the letter model: the hand looks like whatever the test says it does."""

    classes = LETTERS

    def __init__(self):
        self.looks: dict[str, float] = {}

    def probabilities(self, features):
        shares = np.full(len(LETTERS), (1.0 - sum(self.looks.values())) / len(LETTERS))
        for letter, share in self.looks.items():
            shares[LETTERS.index(letter)] += share
        return shares


def spelling(macros=(REELS,), cfg=None, apps=()):
    sim = Sim(cfg, macros=list(macros), apps=list(apps))
    sim.backend.add_window(WindowInfo(1, 500, 400, 800, 600, title="one"))
    sim.reads = sim.engine.letters = Reads()
    return sim


def begin(sim):
    sim.hold(0.4, ("open", *CENTRE))
    sim.hold(0.5, ("ily", *CENTRE))
    assert isinstance(sim.engine.active, SpellInteraction)


def sign(sim, letter, seconds=0.6, pose="neutral", **looks):
    """The hand makes a letter for a while: it looks 90% like it, or as looks says."""
    sim.reads.looks = looks or {letter: 0.9}
    sim.hold(seconds, (pose, *CENTRE))


def test_the_sign_for_i_love_you_is_a_pose_of_its_own_and_takes_a_moment_to_count():
    tracker = PoseTracker(PoseConfig())
    ily = extract_features(make_hand(Config(), SCREEN, "ily", 1000, 900))
    poses = [tracker.update(ily, i / 30.0) for i in range(12)]
    assert poses[7] is Pose.NEUTRAL and poses[-1] is Pose.ILY
    turned = extract_features(make_hand(Config(), SCREEN, "ily", 1000, 900, yaw=60.0))
    tracker = PoseTracker(PoseConfig())
    assert all(tracker.update(turned, i / 30.0) is not Pose.ILY for i in range(12))


def test_spelling_the_letters_of_a_macro_runs_it():
    sim = spelling()
    begin(sim)
    assert sim.engine.overlay.spell == "spelling" and [(o["code"], o["name"], o["done"]) for o in sim.engine.overlay.spell_options] == [("RS", "Instagram Reels", 0)]
    sign(sim, "r", 0.2)
    overlay = sim.engine.overlay
    assert (overlay.spell_letters, overlay.spell_guess, overlay.spell_holding) == ("", "R", "R") and 0 < overlay.spell_hold < 1
    sign(sim, "r", 0.4)
    assert sim.engine.overlay.spell_letters == "R" and not sim.macros.ran
    sign(sim, "s", 0.6, pose="fist")
    assert sim.macros.ran == [REELS] and sim.engine.active is None
    overlay = sim.engine.overlay
    assert (overlay.spell, overlay.spell_letters, overlay.spell_name) == ("done", "RS", "Instagram Reels")
    sim.hold(1.5, ("fist", *CENTRE))  # the S it ended on is a fist, over a window: it closes nothing
    assert not sim.commands("close") and sim.engine.overlay.spell == ""
    assert sim.macros.ran == [REELS]


def test_a_letter_has_to_be_held_and_only_one_that_carries_on_toward_a_macro_is_taken():
    sim = spelling()
    begin(sim)
    sign(sim, "r", 0.25)
    sign(sim, "", 0.3, r=0.0)
    assert sim.engine.active.spelt == ""  # let go of too soon
    sign(sim, "s", 1.0)
    assert sim.engine.active.spelt == "" and sim.engine.overlay.spell_guess == "S"  # no macro begins with S
    # R is taken for U as often as not. Where only R leads anywhere, a hand that looks a good deal like R is one.
    sign(sim, "r", 0.6, u=0.55, r=0.4)
    assert sim.engine.active.spelt == "r" and sim.engine.overlay.spell_guess == "U"
    sign(sim, "s", 0.6, a=0.8, s=0.15)  # but not one that hardly looks like it at all
    assert sim.engine.active is not None and not sim.macros.ran


def test_spelling_is_given_up_after_a_while_with_no_letter():
    sim = spelling()
    begin(sim)
    sign(sim, "r")
    sign(sim, "", 5.0, r=0.0)
    assert sim.engine.active is not None
    sign(sim, "", 1.2, r=0.0)
    assert sim.engine.active is None and not sim.macros.ran
    assert (sim.engine.overlay.spell, sim.engine.overlay.spell_letters) == ("failed", "R")
    # Begun and dropped with nothing spelt, there is nothing to say.
    sim = spelling()
    begin(sim)
    sim.hold(0.6)
    assert sim.engine.active is None and sim.engine.overlay.spell == ""


def test_a_macro_that_is_also_the_start_of_a_longer_one_waits_a_moment_for_more():
    short, long = Macro("r", "Reload", "key", "ctrl+r"), REELS
    sim = spelling([short, long])
    begin(sim)
    sign(sim, "r")
    sign(sim, "", 0.8, r=0.0)
    assert sim.engine.active is not None and not sim.macros.ran
    sign(sim, "", 0.8, r=0.0)
    assert sim.macros.ran == [short] and sim.commands("press_key") == [("press_key", "ctrl+r")]
    sim = spelling([short, long])
    begin(sim)
    sign(sim, "r")
    sign(sim, "s")
    assert sim.macros.ran == [long]


def test_the_sign_made_a_second_time_takes_it_all_back():
    sim = spelling([Macro("r", "Reload", "key", "ctrl+r"), REELS])
    begin(sim)
    sign(sim, "r")
    sim.reads.looks = {}
    sim.hold(0.6, ("ily", *CENTRE))
    assert sim.engine.active is None and not sim.macros.ran and sim.engine.overlay.spell == "failed"
    sim.hold(1.0, ("ily", *CENTRE))  # still held up: it does not begin again by itself
    assert sim.engine.active is None


def test_a_doubled_letter_needs_the_hand_to_be_something_else_in_between():
    sim = spelling([Macro("ll", "Lock", "command", "true")])
    begin(sim)
    sign(sim, "l", 2.0)
    assert sim.engine.active.spelt == "l"  # held on, it is still the one L
    sign(sim, "", 0.4, l=0.0)
    sign(sim, "l")
    assert [macro.name for macro in sim.macros.ran] == ["Lock"]


def test_with_no_macros_the_sign_begins_nothing():
    sim = Sim()
    sim.hold(0.4, ("open", *CENTRE))
    sim.hold(1.0, ("ily", *CENTRE))
    assert sim.engine.active is None and sim.engine.letters is None and sim.engine.overlay.spell == ""


def test_nothing_else_starts_while_spelling_and_a_lost_hand_ends_it():
    sim = spelling()
    begin(sim)
    sign(sim, "", 1.0, pose="fist")  # a fist over a window, which would close it
    sign(sim, "", 1.0, pose="two_finger")
    assert isinstance(sim.engine.active, SpellInteraction) and not sim.backend.commands and sim.backend.scrolled == 0
    sim.hold(0.5)
    assert sim.engine.active is None


def test_the_model_that_comes_with_holotouch_is_what_the_engine_reads_with(tmp_path):
    sim = Sim(macros=[REELS])
    assert sim.engine.letters.classes == LETTERS
    cfg = Config()
    cfg.spell.model = str(tmp_path / "none.npz")
    with pytest.raises(ValueError, match="spell.*model.*none.npz"):
        Sim(cfg, macros=[REELS])


def test_macros_are_read_from_a_file_and_checked(tmp_path):
    assert load_macros(tmp_path / "none.toml") == [REELS]
    assert [m.letters for m in load_macros(REPO / "contrib" / "macros.example.toml")] == ["rs", "yt", "t", "f", "hi"]
    path = tmp_path / "macros.toml"
    path.write_text('[[macro]]\nletters = "RS"\nname = "Reels"\ntype = "url"\ndata = "https://example.org"\n')
    assert load_macros(path) == [Macro("rs", "Reels", "url", "https://example.org")]
    path.write_text(path.read_text() * 2)
    with pytest.raises(ValueError, match="two macros are spelt RS"):
        load_macros(path)
    with pytest.raises(ValueError, match="J cannot be spelt.*drawn in the air"):
        macro_from_dict({"letters": "jo", "data": "true"})
    with pytest.raises(ValueError, match="2 cannot be spelt"):
        macro_from_dict({"letters": "r2", "data": "true"})
    with pytest.raises(ValueError, match="unknown macro type 'open'"):
        macro_from_dict({"letters": "a", "type": "open", "data": "x"})
    with pytest.raises(ValueError, match="no data"):
        macro_from_dict({"letters": "a", "type": "url"})
    with pytest.raises(ValueError, match="no letters"):
        macro_from_dict({"name": "Nothing", "data": "true"})


def test_macros_know_which_letters_carry_on_and_do_what_their_type_says():
    backend = FakeBackend()
    spawned = []
    macros = Macros(
        backend,
        [REELS, Macro("r", "Reload", "key", "ctrl+r"), Macro("hi", "Greet", "text", "hello"), Macro("t", "Terminal", "command", "xterm"),
         Macro("f", "Files", "app", "thunar.desktop")],
    )  # fmt: skip
    macros._spawn = lambda command, shell: spawned.append((command, shell))
    assert macros.next_letters("") == {"r", "h", "t", "f"} and macros.next_letters("r") == {"s"} and macros.next_letters("rs") == set()
    assert macros.exact("r").name == "Reload" and macros.exact("h") is None
    assert [m.letters for m in macros.toward("r")] == ["rs", "r"]
    for macro in macros.macros:
        macros.run(macro)
    assert backend.commands == [("press_key", "ctrl+r"), ("type_text", "hello")]
    assert spawned == [
        (["xdg-open", "https://www.instagram.com/reels/"], False), ("xterm", True), (["gtk-launch", "thunar.desktop"], False),
    ]  # fmt: skip
    assert not Macros(backend, [])


def test_the_overlay_is_told_what_has_been_spelt():
    bridge = Bridge(Config())
    changes = []
    bridge.spellOptionsChanged.connect(lambda: changes.append(1))
    state = OverlayState(spell="spelling", spell_letters="R", spell_guess="S", spell_holding="S", spell_hold=0.5)
    state.spell_options = [{"name": "Instagram Reels", "icon": "", "code": "RS", "done": 1, "chosen": False}]
    state.spell_more, state.spell_opening = 3, 0.25
    bridge.apply(state)
    bridge.apply(state)
    fx = bridge.fx
    assert (fx["spell"], fx["spellLetters"], fx["spellGuess"], fx["spellHolding"], fx["spellHold"]) == ("spelling", "R", "S", "S", 0.5)
    assert (fx["spellMore"], fx["spellOpening"], fx["spellName"]) == (3, 0.25, "")
    assert bridge.spellOptions == [{**state.spell_options[0], "hasIcon": False}] and changes == [1]
    # Once spelling is over the rows stay as they were, for the launcher to fade out with.
    bridge.apply(OverlayState(spell="done", spell_letters="RS", spell_name="Instagram Reels"))
    assert bridge.spellOptions[0]["name"] == "Instagram Reels" and changes == [1]


def test_the_sign_is_scored_as_beginning_to_spell():
    report = score([session(["ily", "relaxed"], shown={"ily": ("ily", 0), "relaxed": ("point", 0)})], Config())
    assert report.right("ily") == 1.0 and report.ran == report.holds and not report.strays


def test_an_app_is_spelt_by_its_name_until_no_other_begins_the_same_way_and_opens_after_a_moment():
    sim = spelling(apps=[FILES, ROLLER, FIREFOX])
    begin(sim)
    overlay = sim.engine.overlay
    # The macro is listed first, by its letters, and then the apps, by their names.
    assert [(o["code"], o["name"]) for o in overlay.spell_options] == [
        ("RS", "Instagram Reels"), ("", "Files"), ("", "File Roller"), ("", "Firefox"),
    ]  # fmt: skip
    assert overlay.spell_options[3]["icon"] == "firefox" and overlay.spell_more == 0
    sign(sim, "f")
    sign(sim, "i")
    overlay = sim.engine.overlay
    assert [(o["name"], o["done"], o["chosen"]) for o in overlay.spell_options] == [
        ("Files", 2, False), ("File Roller", 2, False), ("Firefox", 2, False),
    ]  # fmt: skip
    assert overlay.spell_opening == 0.0
    sign(sim, "r")
    overlay = sim.engine.overlay
    assert [(o["name"], o["done"], o["chosen"]) for o in overlay.spell_options] == [("Firefox", 3, True)]
    assert 0.0 < overlay.spell_opening < 1.0 and not sim.macros.ran  # it waits a moment, for more letters or to be taken back
    sign(sim, "", 1.2, r=0.0)
    assert sim.macros.ran == [FIREFOX] and sim.engine.active is None
    overlay = sim.engine.overlay
    assert (overlay.spell, overlay.spell_letters, overlay.spell_name) == ("done", "FIR", "Firefox")


def test_an_app_spelt_in_full_opens_at_once_and_one_only_begun_can_be_taken_back():
    sim = spelling(apps=[FILES, ROLLER, FIREFOX])
    begin(sim)
    for letter in "file":
        sign(sim, letter)
    assert [o["name"] for o in sim.engine.overlay.spell_options] == ["Files", "File Roller"] and not sim.macros.ran
    sign(sim, "s")
    assert sim.macros.ran == [FILES]
    sim = spelling(apps=[FILES, ROLLER, FIREFOX])
    begin(sim)
    for letter in "fir":
        sign(sim, letter)
    sim.reads.looks = {}
    sim.hold(0.6, ("ily", *CENTRE))  # the sign again, before the wait is over
    assert sim.engine.active is None and sim.engine.overlay.spell == "failed"
    sim.hold(1.5, ("ily", *CENTRE))
    assert not sim.macros.ran


def test_a_macro_has_to_be_spelt_in_full_even_where_nothing_else_begins_as_it_does():
    ristretto = app("Ristretto")
    sim = spelling([REELS], apps=[ristretto])
    begin(sim)
    sign(sim, "r")
    assert [o["name"] for o in sim.engine.overlay.spell_options] == ["Instagram Reels", "Ristretto"]
    sign(sim, "s")
    assert sim.macros.ran == [REELS]
    # A macro's letters are its own before they are the start of an app's name.
    reload = Macro("r", "Reload", "key", "ctrl+r")
    sim = spelling([reload], apps=[ristretto])
    begin(sim)
    sign(sim, "r")
    assert [(o["name"], o["chosen"]) for o in sim.engine.overlay.spell_options] == [("Reload", True), ("Ristretto", False)]
    sign(sim, "", 1.4, r=0.0)
    assert sim.macros.ran == [reload]


def test_the_launcher_lists_the_first_few_and_counts_the_rest():
    apps = [app(f"Kate {'abcdefghik'[n]}") for n in range(10)]
    sim = spelling([], apps=apps)
    begin(sim)
    overlay = sim.engine.overlay
    assert [o["name"] for o in overlay.spell_options] == [a.name for a in apps[:6]] and overlay.spell_more == 4
    for letter in "kate":
        sign(sim, letter)
    sign(sim, "h")
    assert sim.macros.ran == [apps[7]]


def test_names_are_spelt_without_what_cannot_be_spelt():
    assert letters_of("Visual Studio Code") == "visualstudiocode" and letters_of("Qt 6 Designer") == "qtdesigner"
    assert letters_of("Élan café") == "elancafe"
    # J and Z are drawn in the air: the hand that draws J is the hand of I, and Z's that of D.
    assert letters_of("FileZilla") == "filedilla" and letters_of("Joplin") == "ioplin"
    assert [covered("Qt 6 Designer", n) for n in (0, 1, 2, 3, 10, 11)] == [0, 1, 2, 6, 13, 13]


def desktop_file(directory, name, **keys):
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = {"Type": "Application", "Exec": "true", **keys}
    path.write_text("[Desktop Entry]\n" + "".join(f"{key}={value}\n" for key, value in keys.items()) + "[Desktop Action new]\nName=New\n")


def test_installed_apps_are_those_the_applications_menu_lists(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "XFCE")
    home, system = tmp_path / "home", tmp_path / "system"
    desktop_file(system, "firefox.desktop", Name="Firefox", Icon="firefox", **{"Name[de]": "Feuerfuchs"})
    desktop_file(system, "kde/kate.desktop", Name="Kate")
    desktop_file(system, "zoom.desktop", Name="Zoom")
    desktop_file(system, "2048.desktop", Name="2048")
    desktop_file(system, "quiet.desktop", Name="Quiet", NoDisplay="true")
    desktop_file(system, "gone.desktop", Name="Gone", TryExec="holotouch-no-such-program")
    desktop_file(system, "left.desktop", Name="Left Behind", Exec="holotouch-no-such-program --flag %U")
    desktop_file(system, "gnome.desktop", Name="Gnome Only", OnlyShowIn="GNOME;")
    desktop_file(system, "xfce.desktop", Name="Xfce Only", OnlyShowIn="XFCE;")
    desktop_file(system, "notxfce.desktop", Name="Not Xfce", NotShowIn="XFCE;")
    desktop_file(system, "link.desktop", Name="Link", Type="Link")
    desktop_file(system, "removed.desktop", Name="Removed")
    desktop_file(home, "removed.desktop", Name="Removed", Hidden="true")  # hidden by the user's own file of that name
    desktop_file(home, "firefox.desktop", Name="Firefox Nightly")
    (system / "broken.desktop").write_bytes(b"\xff\xfe not a desktop file")
    apps = installed_apps([home, system, tmp_path / "none"])
    assert [(a.letters, a.name, a.data) for a in apps] == [
        ("firefoxnightly", "Firefox Nightly", "firefox.desktop"), ("kate", "Kate", "kde-kate.desktop"),
        ("xfceonly", "Xfce Only", "xfce.desktop"), ("doom", "Zoom", "zoom.desktop"),
    ]  # fmt: skip
    assert all(a.type == "app" and a.by_name for a in apps)


def test_of_two_things_spelt_alike_the_macro_or_the_first_app_is_kept():
    terminal = Macro("terminal", "Terminal", "command", "xterm")
    macros = Macros(FakeBackend(), [terminal], [app("Terminal"), app("IDA 9.1", "ida91.desktop"), app("IDA 9.3", "ida93.desktop"), FIREFOX])
    assert [a.data for a in macros.apps] == ["ida91.desktop", "firefox.desktop"]
    assert macros.exact("terminal") is terminal and macros.next_letters("") == {"t", "i", "f"}
    assert macros.chosen("") is None and macros.chosen("f") is FIREFOX and macros.chosen("t") is None
    assert macros.chosen("terminal") is terminal and macros.chosen("x") is None


def test_the_installed_apps_are_looked_for_unless_the_config_says_not_to(monkeypatch):
    monkeypatch.setattr("holotouch.launcher.macros.load_macros", lambda: [])
    monkeypatch.setattr("holotouch.core.engine.installed_apps", lambda: [FIREFOX])
    assert Engine(Config(), FakeBackend(SCREEN)).macros.apps == [FIREFOX]
    cfg = Config()
    cfg.spell.apps = False
    engine = Engine(cfg, FakeBackend(SCREEN))
    assert not engine.macros and engine.letters is None

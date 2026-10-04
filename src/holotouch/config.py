"""Typed configuration with defaults, optionally overridden by ~/.config/holotouch/config.toml."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "holotouch"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "holotouch"
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
CONFIG_PATH = CONFIG_DIR / "config.toml"
MENU_PATH = CONFIG_DIR / "menu.toml"
MACROS_PATH = CONFIG_DIR / "macros.toml"
SOCKET_PATH = RUNTIME_DIR / "holotouch.sock"
# The control panel sends the output of the HoloTouch it starts to LOG_PATH, and names that file to
# it in this environment variable, so that a panel opened later knows where to read.
LOG_PATH = CACHE_DIR / "holotouch.log"
LOG_ENV = "HOLOTOUCH_LOG"


@dataclass
class CameraConfig:
    device: str = "/dev/video0"
    width: int = 1280
    height: int = 720
    fps: int = 30
    mirror: bool = True
    # Disable low-light frame-rate halving and set the anti-flicker frequency on start.
    fix_controls: bool = True
    power_line_hz: int = 60


@dataclass
class TrackerConfig:
    num_hands: int = 2
    detection_confidence: float = 0.5
    presence_confidence: float = 0.5
    tracking_confidence: float = 0.5
    # The face is tracked too, for the fist-to-chin gesture, this many times a second.
    face: bool = True
    face_hz: float = 15.0
    # With no hands in view for this long, only every second frame is processed.
    idle_after_s: float = 3.0
    stall_restart_s: float = 2.0


@dataclass
class MappingConfig:
    # Region of the mirrored camera frame (fractions) that maps to the whole screen.
    box_x: float = 0.15
    box_y: float = 0.20
    box_w: float = 0.70
    box_h: float = 0.60
    overshoot: float = 0.04


@dataclass
class FilterConfig:
    # 1€ filter on the hand position, in screen heights. min_cutoff (Hz) is how hard a slow hand
    # is smoothed: lower removes more jitter. beta is how much the cutoff rises per unit of speed:
    # higher removes more lag from a fast hand.
    min_cutoff: float = 1.5
    beta: float = 12.0
    # The same filter on the finger landmarks, in metres, which the poses are read from...
    landmark_min_cutoff: float = 4.0
    landmark_beta: float = 60.0
    # ...and on the finger tilt that sets the scroll speed, in degrees.
    tilt_min_cutoff: float = 1.0
    tilt_beta: float = 0.03
    d_cutoff: float = 1.0  # cutoff of the speed estimate, shared by all three
    velocity_cutoff: float = 5.0
    predict_max_ms: float = 50.0
    follow_tau_ms: float = 12.0
    lost_grace_ms: float = 250.0


@dataclass
class PoseConfig:
    # Thumb-tip to fingertip distance divided by palm length (wrist to middle knuckle).
    # Touching fingertips measure about 0.15; a relaxed hand sits near 0.4 to 0.6.
    pinch_enter: float = 0.25
    pinch_exit: float = 0.42
    # A pinky pinch must be nearer the thumb than the other fingertips by this factor.
    pinch_margin: float = 1.3
    pinch_on_ms: float = 30.0
    pinch_off_ms: float = 60.0
    # Fingertip to knuckle distance divided by palm length; all four below this is a fist.
    # Curled fingers measure 0.2 to 0.55, relaxed ones 0.6 and up.
    fist_enter: float = 0.58
    fist_exit: float = 0.68
    fist_on_ms: float = 90.0
    # Finger straightness (tip-to-knuckle distance over summed bone lengths).
    # A flat open hand is above 0.96; a relaxed, slightly curled one is around 0.9.
    extend_enter: float = 0.94
    extend_exit: float = 0.90
    pose_on_ms: float = 80.0
    # A claw, as if gripping a knob: every finger bent, by this much straightness, with the thumb
    # at least claw_thumb palm lengths clear of every fingertip. A real claw measures 0.63 to 0.80
    # with the thumb 0.42 to 0.56 clear; a relaxed hand 0.91 and up; a fist 0.6 and under.
    claw_min: float = 0.58
    claw_max: float = 0.86
    claw_thumb: float = 0.38
    claw_on_ms: float = 300.0
    # The letter Y of the manual alphabet, thumb and pinky out and the rest folded, has to be held
    # this long before it counts: it opens the microphone.
    y_on_ms: float = 300.0
    # So does the sign for "I love you", index and pinky up and the two fingers between them
    # folded: it begins spelling.
    ily_on_ms: float = 300.0
    # A hand must be tracked and open/relaxed this long before its gestures count.
    arm_ms: float = 150.0
    # A hand must point, with its thumb held out, this long before the thumb coming down presses
    # the mouse button. Fingers folding into a point get there before the thumb does, and for
    # that moment look just like taking aim.
    aim_ms: float = 200.0
    # Pinches that start while the hand moves faster than this (screen heights/s) are ignored.
    max_onset_speed: float = 2.5
    # A hand turned further from the camera than this (see HandFeatures.facing) is read less
    # surely, so its pinch has to start slower still. Real side-on pinches began at 0.45 and
    # under; the pinches a waving or scratching hand was misread as, at 0.74 and over.
    turned_facing: float = 0.73
    turned_onset_speed: float = 0.6
    # A model saved by `holotouch train`. When set, it reads the pose and the thresholds above
    # that tell one pose from another are not used; the timings still are.
    model: str = ""


@dataclass
class GestureConfig:
    flick_speed: float = 2.0  # screen heights per second
    flick_ratio: float = 1.5  # vertical speed must exceed horizontal by this factor
    flick_window_ms: float = 250.0
    edge_margin: float = 0.02  # fraction of screen width
    edge_dwell_ms: float = 350.0
    edge_cooldown_ms: float = 900.0
    wrap_workspaces: bool = False
    close_dwell_ms: float = 700.0
    close_radius: float = 0.06  # screen heights the fist may drift
    # An open palm swept fast to the right presses the Enter key in whatever has the keyboard.
    swipe_min_travel: float = 0.30  # screen widths
    swipe_window_ms: float = 350.0
    swipe_ratio: float = 2.5
    swipe_cooldown_ms: float = 700.0
    swipe_min_facing: float = 0.5
    # No longer used: a swipe does not switch workspaces any more. Kept so that a config that
    # sets it still loads.
    swipe_natural: bool = True
    # Hands clapped twice open a new tab, when the window that has the keyboard is a web browser.
    # A clap is the two palms this many metres apart or more, then this near or nearer, within
    # clap_close_ms. Two claps within clap_window_ms are the pair.
    clap_apart: float = 0.14
    clap_together: float = 0.08
    clap_close_ms: float = 350.0
    clap_window_ms: float = 900.0
    # The browsers, each by a word of its window class: "Google-chrome" has the word chrome.
    clap_browsers: str = (
        "chrome chromium thorium firefox librewolf waterfox floorp zen brave vivaldi opera edge "
        "falkon konqueror epiphany midori tor"
    )
    # A closed hand touched to the chin opens the window switcher.
    chin_reach: float = 0.3  # how near the chin some part of the hand must come, in face heights
    # How much nearer the camera than the face the hand may look (1.0 = level with the face).
    # A fist under the chin measures 1.0 to 1.35; a hand held out in front of the face, 1.5 to 2.
    chin_depth: float = 1.5
    # How curled every finger must be, measured like pose.fist_enter but looser: a fist against
    # the face is partly hidden, and its fingers measure up to 0.72.
    chin_curl: float = 0.78
    chin_hold_ms: float = 250.0
    # Scrolling is set by how far the two extended fingers tilt from where they rest.
    scroll_dead_deg: float = 8.0  # tilt smaller than this does not scroll
    scroll_full_deg: float = 40.0  # tilt toward the camera, from where the fingers rest, that gives the top speed
    # Fingers have less room to lean back than to tip forward: this lean back gives the top speed.
    scroll_up_full_deg: float = 25.0
    # Fingers that lean toward the camera by less than this, as HandFeatures.finger_tilt reads it,
    # are only resting, however far that is from where they first came to rest: a hand held up
    # relaxes forward. Tipped further than this, and than the dead zone, they scroll down.
    scroll_down_from_deg: float = 60.0
    scroll_speed: float = 20.0  # top speed in wheel notches per second
    scroll_invert: bool = False  # true: tilting the fingers down scrolls up
    scroll_backend: str = "auto"  # auto | uinput | xtest
    # Turning a claw like a knob changes the volume (right hand) or the screen brightness (left).
    knob_dead_deg: float = 8.0  # a turn smaller than this changes nothing
    knob_full_deg: float = 120.0  # the turn that takes it from nothing to full
    knob_invert: bool = False  # true: turning clockwise turns it down
    # Both hands holding up two fingers, the peace sign, for this long open the camera app.
    camera_hold_ms: float = 3000.0
    # The app to open, as a shell command. Empty: the first installed of snapshot, cheese, kamoso
    # and guvcview. HoloTouch gives up the webcam while it runs, and tracks no hands until it is closed.
    camera_command: str = ""
    # Once the app's window has been up for camera_shutter_ms, this key is pressed in it to take
    # a photo: "t" is Snapshot's. One character, or space or Return; empty presses nothing.
    camera_shutter_key: str = "t"
    camera_shutter_ms: float = 3000.0
    # The letter Y of the manual alphabet, held up, dictates: the microphone is recorded for as long
    # as the sign is held, and what was said is then typed into whatever has the keyboard.
    # The command that turns the recording into text, run by the shell with {file} replaced by a
    # 16 kHz mono WAV file. It prints the text, or JSON with a "text" field. Empty: Handy's
    # (`handy --transcribe-file`), if Handy is installed.
    dictate_command: str = ""
    dictate_max_s: float = 120.0  # the longest one recording may be; it is written out then
    dictate_trailing_space: bool = True  # a space after what was said, so that the next follows on
    resize_gain: float = 1.0
    resize_hz: float = 60.0
    min_window_w: int = 200
    min_window_h: int = 120
    # A grab leaves the window alone until the pinch has lasted this long, and one that is over
    # within grab_undo_ms without having been a tap is undone: the window goes back as it was.
    # A hand misread as pinching seldom stays that way for longer.
    grab_confirm_ms: float = 150.0
    grab_undo_ms: float = 300.0
    # A quick pinch on a window that goes nowhere is a tap: it brings the window to the front.
    tap_ms: float = 400.0  # longest a pinch may last and still count as a tap
    # Screen heights the hand may drift during a tap; a maximized window is pulled free beyond it.
    tap_radius: float = 0.05
    tap_speed: float = 0.5  # screen heights per second; a hand moving faster is dragging, not tapping
    # A pointing hand's thumb, brought down, holds the left mouse button down where the cursor is.
    # The pointer stays there until the hand has moved this many screen heights, and then follows it:
    # short of that it is a click, past it a drag. A hand held still wanders about 0.02.
    click_slop: float = 0.03


@dataclass
class SpellConfig:
    # The sign for "I love you" opens the launcher: the letters of the manual alphabet that the
    # hand goes on to make are read, and the macro they spell is run (~/.config/holotouch/macros.toml),
    # or the app whose name they begin is opened.
    apps: bool = True  # false: only the macros can be spelt, not the installed apps
    # The model that reads a letter from the hand. Empty: ~/.config/holotouch/letters.npz, if
    # `holotouch train-letters` has made one from your own hand, and otherwise the one HoloTouch comes with.
    model: str = ""
    hold_ms: float = 400.0  # how long a letter has to be held before it counts
    # Only the letters that carry on toward some macro or app are looked for. The hand has to look this
    # much like one of them, as a share of one, even where it looks more like some other letter.
    min_confidence: float = 0.35
    # The same letter counts a second time only once the hand has been something else for this long.
    repeat_ms: float = 250.0
    # Where what has been spelt is a macro or an app's whole name, and the start of a longer one
    # too, it is opened once no further letter has come for this long. So is an app whose name has
    # only been begun, once no other begins the same way.
    settle_ms: float = 1200.0
    timeout_ms: float = 6000.0  # with no letter for this long, spelling is given up
    # For this long after spelling the hand starts no gesture: its last letter is a fist as likely as not.
    rest_ms: float = 700.0


@dataclass
class PieConfig:
    # Pixel sizes before ui.scale is applied. The dead zone and the stroke length follow Fly-Pie;
    # the petals are larger and further out than its items, and the seed is drawn to the dead zone.
    dead_zone: float = 51.0
    stroke_length: float = 150.0
    child_offset: float = 140.0
    child_size: float = 76.0
    center_size: float = 108.0
    max_items: int = 12


@dataclass
class SwitcherConfig:
    # Pixel sizes before ui.scale is applied.
    card_w: float = 260.0
    card_h: float = 250.0
    gap: float = 40.0
    columns: int = 6  # most cards in one row
    all_workspaces: bool = True
    thumbnails: bool = True
    # The switcher closes once no hand has been in view for this long.
    idle_close_ms: float = 1500.0


@dataclass
class UiConfig:
    scale: float = 1.6
    # No longer used: the colours are HoloTouch's own now (holotouch/theme.py), with one for each hand.
    # Kept so that a config that sets them still loads.
    accent: str = "#00e5ff"
    danger: str = "#ff4d5e"
    debug: bool = False
    hud_ms: float = 1200.0
    tick_hz: float = 0.0  # 0 = display refresh rate


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    mapping: MappingConfig = field(default_factory=MappingConfig)
    filter: FilterConfig = field(default_factory=FilterConfig)
    pose: PoseConfig = field(default_factory=PoseConfig)
    gesture: GestureConfig = field(default_factory=GestureConfig)
    spell: SpellConfig = field(default_factory=SpellConfig)
    pie: PieConfig = field(default_factory=PieConfig)
    switcher: SwitcherConfig = field(default_factory=SwitcherConfig)
    ui: UiConfig = field(default_factory=UiConfig)


def _apply(obj, data: dict, path: str) -> None:
    known = {f.name: f for f in fields(obj)}
    for key, value in data.items():
        if key not in known:
            raise ValueError(f"unknown config key: {path}{key}")
        current = getattr(obj, key)
        if is_dataclass(current):
            if not isinstance(value, dict):
                raise ValueError(f"config key {path}{key} must be a table")
            _apply(current, value, f"{path}{key}.")
        elif isinstance(current, bool):
            if not isinstance(value, bool):
                raise ValueError(f"config key {path}{key} must be true or false")
            setattr(obj, key, value)
        elif isinstance(current, (int, float)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"config key {path}{key} must be a number")
            setattr(obj, key, type(current)(value))
        else:
            if not isinstance(value, str):
                raise ValueError(f"config key {path}{key} must be a string")
            setattr(obj, key, value)


def load_config(path: Path | None = None) -> Config:
    cfg = Config()
    path = path or CONFIG_PATH
    if path.exists():
        with open(path, "rb") as fh:
            _apply(cfg, tomllib.load(fh), "")
    return cfg

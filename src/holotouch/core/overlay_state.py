"""What the overlay should draw this tick. Built by the engine, rendered by the QML layer."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class HandView:
    id: int
    x: float
    y: float
    pinch: float
    pose: str
    active: bool  # this hand is driving the current interaction
    armed: bool
    scroll: float = 0.0  # -1..1 while this hand is scrolling; positive is down
    side: str = "right"  # "left" or "right", as the user sees their own hands


@dataclass(slots=True)
class FrameView:
    x: float
    y: float
    w: float
    h: float
    mode: str  # hover | grab | resize | close
    label: str = ""  # the size while resizing; the window's title while closing
    side: str = ""  # the hand it belongs to: "left" or "right"; "" when two hands share it
    ghost: tuple[float, float, float, float] | None = None  # the outline a resize began with


@dataclass(slots=True)
class OverlayState:
    hands: list[HandView] = field(default_factory=list)
    frame: FrameView | None = None
    edge_side: int = 0  # -1 left, 1 right, 0 none
    edge_progress: float = 0.0
    edge_target: int = -1  # the workspace a window held at that edge will go to
    close_progress: float = 0.0
    close_x: float = 0.0
    close_y: float = 0.0
    hud_desktop: int = -1  # -1 hides the workspace HUD
    hud_count: int = 0
    menu: dict | None = None
    switcher: dict | None = None
    scrolling: bool = False
    knob: float = -1.0  # 0..1 while a knob is held; -1 hides it
    knob_x: float = 0.0
    knob_y: float = 0.0
    knob_name: str = ""  # what it turns: "Volume" or "Brightness"
    hold_progress: float = 0.0  # how far a sign held with both hands has got; 0 hides its ring
    hold_x: float = 0.0
    hold_y: float = 0.0
    hold_name: str = ""  # what the sign opens: "Camera"
    click: bool = False  # for a moment after the mouse button goes down, at click_x, click_y
    click_x: float = 0.0
    click_y: float = 0.0
    # "listening" while the microphone is recorded, "writing" while that is turned into text, and
    # "failed" for a moment when it could not be; "" otherwise. The engine only ever says the first.
    dictation: str = ""
    # "spelling" while the launcher is open and letters are read, and for a moment after: "done"
    # when they opened something, "failed" when they were given up; "" otherwise.
    spell: str = ""
    spell_letters: str = ""  # the letters taken so far
    spell_guess: str = ""  # the letter the hand looks like now, if it clearly looks like one
    spell_holding: str = ""  # the letter being held that would carry on toward a macro or app, and how far
    spell_hold: float = 0.0  # it has got toward being taken
    # The first few macros and apps still within reach, and how many more there are. Each has its
    # name and icon, its letters as code where they are not its name, how many characters have
    # been spelt as done, and whether it is the one chosen: what is opened if no more letters come.
    spell_options: list[dict] = field(default_factory=list)
    spell_more: int = 0
    spell_opening: float = 0.0  # how far the wait for more letters has got, before the chosen one is opened
    spell_name: str = ""  # what was opened
    # For a moment after a gesture does what cannot be seen: what that was, "Enter", "New tab" or
    # "Play / pause". Whoever runs the engine says here how the page tossed to the phone is getting on, too.
    key: str = ""
    track: int = 0  # for a moment after a track is skipped: 1 for the next one, -1 for the one before
    paused: bool = False

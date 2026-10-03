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


@dataclass(slots=True)
class FrameView:
    x: float
    y: float
    w: float
    h: float
    mode: str  # hover | grab | resize | close
    label: str = ""


@dataclass(slots=True)
class OverlayState:
    hands: list[HandView] = field(default_factory=list)
    frame: FrameView | None = None
    edge_side: int = 0  # -1 left, 1 right, 0 none
    edge_progress: float = 0.0
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
    track: int = 0  # for a moment after a track is skipped: 1 for the next one, -1 for the one before
    paused: bool = False

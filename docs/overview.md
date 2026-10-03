# HoloWM: what it does and how it works

HoloWM lets you control the windows on a Linux desktop with your hands in the air. A webcam watches
your hands, HoloWM reads what they are doing, and it moves, resizes, closes, scrolls and switches
windows accordingly. A see-through overlay on the screen shows where your hands are and what each
gesture is about to do.

It runs on X11 with the XFCE window manager (xfwm4), on a laptop CPU, with an ordinary webcam.

## What you can do with it

Each hand is shown on screen as a ring cursor. A region in the middle of the camera's view maps to
the whole screen, so the hand never has to reach the edge of the picture.

| Hand shape | What it does | How |
| --- | --- | --- |
| Thumb + index pinch | Move a window | Pinch over a window and carry it. A quick pinch that goes nowhere only brings the window to the front. |
| Second hand pinches too | Resize | While one hand holds a window, the other pinches and the two pull apart or together. |
| Flick a held window | Maximize or minimize | Flick it up and let go to maximize, down to minimize. |
| Hold a window at a screen edge | Send to another workspace | Carry it to the left or right edge and wait; the window and the view move to the next workspace. |
| Thumb + middle pinch | Left mouse button | One pinch is a click, two a double click. Keep it pinched and move to drag. |
| Thumb + pinky pinch | Pie menu | A ring of items opens at the hand. Move toward one and let go to pick it. |
| Fist, held still over a window | Close the window | A ring fills for about 0.7 s; moving or opening the hand cancels it. |
| Two fingers up | Scroll | Tilt the two fingers down or back. The further the tilt, the faster the scroll. |
| Claw, turned like a knob | Volume or brightness | Right hand turns the volume, left hand the screen brightness. |
| Open palm, swept sideways | Switch workspace | A fast sweep to the left or right. |
| Fist touched to the chin | Window switcher | Every window is laid out as a card with a picture of it. Point at one and pinch to go to it. |
| Peace sign with both hands | Camera | Held for 3 s, it opens the camera app and takes a photo. Tracking pauses until the app is closed, since only one program can use the webcam. |

The pie menu starts apps (terminal, browser, files), skips music tracks, lists the running windows,
maximizes, minimizes, tiles or closes the window under the hand, and switches workspaces. Its
contents can be replaced with `~/.config/holowm/menu.toml` (see `contrib/menu.example.toml`).

## How it works

HoloWM is three kinds of process:

1. **The tracker** reads the webcam and finds hands and a face in each frame.
2. **The core** turns those into gestures, acts on windows, and draws the overlay.
3. **The control panel** is an optional window that starts, stops and watches the core.

### 1. Tracker: camera to landmarks

`src/holowm/tracker/`

- The webcam is read through V4L2 at 1280×720 and 30 frames a second, and each frame is mirrored
  so that moving a hand to the right moves its cursor to the right.
- MediaPipe finds up to two hands per frame and gives 21 landmarks for each, both as positions in
  the picture and as a 3D shape in metres. A face mesh is found about 15 times a second, for the
  chin gesture.
- Each result is sent to the core over a pipe as a `FrameSample`, stamped with when the frame was
  captured.
- With no hands in view for 3 s it processes only every second frame, to save power.
- It runs in a process of its own so that model inference never stalls the overlay. The core
  restarts it if it dies or stops sending.

### 2. Core: landmarks to gestures

`src/holowm/core/`

**Hand tracks** (`hands.py`). Detections are matched to the hands already being followed, so each
hand keeps its identity when hands cross or drop out for a moment. A hand that vanishes is kept for
a quarter of a second before it is forgotten.

**Smoothing** (`filters.py`). Positions pass through a 1€ filter, which smooths a slow hand hard
(no jitter) and a fast hand lightly (no lag). The camera gives 30 samples a second and the screen
refreshes faster, so the position is predicted forward between samples from the hand's speed.

**Poses** (`poses.py`). From the landmarks HoloWM measures a few things in palm lengths: how far
the thumb tip is from each fingertip, how curled and how straight each finger is, how squarely the
palm faces the camera, and how far the fingers tilt. Hand-written rules turn these into one of
eight poses: neutral, open, index pinch, middle pinch, pinky pinch, fist, two fingers, claw. Each
pose has separate thresholds for entering and leaving, and must persist for a short time before it
counts, so a pose does not flicker.

**Face** (`face.py`). The face mesh gives the chin's position and the face's size, which tell how
near the chin a hand is, and whether it is level with the face or held out in front of it.

**The engine** (`engine.py`, `interactions/`). On every tick the engine looks at each hand's pose
and starts the matching interaction: move, click, pie menu, close, scroll, knob, window switcher or
camera. One interaction runs at a time and owns its hands until it ends.

Several guards keep misread hands from doing damage:

- A hand must be in view and relaxed for a moment before its gestures count.
- A pinch that begins while the hand is moving fast is ignored.
- A grab leaves the window alone for the first 150 ms, and a grab shorter than 300 ms is undone.
- Only application windows can be changed, never the desktop or a panel, and fullscreen windows
  are not grabbed.

A small trained pose model exists as an alternative to the rules (`pose_model.py`, `holowm train`).
It is off by default and the rules are what HoloWM uses.

### 3. Acting on the desktop

`src/holowm/x11/`

The engine talks to a `WindowBackend` interface (`core/actions.py`), which has two implementations:

- **`X11Backend`** keeps a cached model of xfwm4's windows, updated from X events, and changes them
  with standard EWMH requests: move, resize, maximize, minimize, close, activate, switch workspace.
  Clicks and key presses go through XTEST. Scrolling uses a virtual mouse on `/dev/uinput` for
  smooth high-resolution wheel events, and falls back to XTEST steps. Volume is set with `pactl`,
  brightness through `/sys/class/backlight`, and tracks are skipped with `playerctl`.
- **`FakeBackend`** holds windows in memory only. Tests use it, and so does practice mode
  (`--dry-run`), where gestures act on two stand-in windows.

### 4. The overlay

`src/holowm/overlay/`

A fullscreen, transparent, click-through window drawn with Qt Quick sits above everything. The
engine produces an `OverlayState` each tick and a bridge hands it to QML, which draws:

- a ring cursor for each hand, closing as the pinch closes
- a frame around the window under the hand, or the one being moved or resized
- the pie menu and the window switcher
- progress rings for closing a window and for the camera sign
- the volume or brightness knob, a click pulse, a glow at the screen edge
- brief notes for the workspace switched to and the track skipped
- an optional diagnostics panel showing frame rate, latency, each hand's pose and measurements,
  and the hands and face as the camera sees them

The core also has a tray icon (pause, diagnostics, quit) and a control socket.

### 5. The control panel

`src/holowm/panel/`

`holowm panel` opens a window from which HoloWM is started and stopped without a terminal.
`holowm panel --install` adds it to the applications menu. It shows:

- a Start/Stop button, the live frame rate, the number of hands in view and the gesture in progress
- a button to pause and resume tracking
- switches for the diagnostics view and for practice mode
- a guide to the gestures
- the results of the machine checks
- HoloWM's log

The panel starts HoloWM as a separate process and follows it over the control socket, so closing
the panel leaves HoloWM running, and a HoloWM started from a terminal is picked up as well.

## Commands

| Command | What it does |
| --- | --- |
| `holowm run` | Start tracking and the overlay. This is the default with no command. |
| `holowm run --debug` | The same, with the diagnostics panel shown. |
| `holowm run --dry-run` | Act on stand-in windows instead of real ones. |
| `holowm run --replay FILE [--loop]` | Drive the engine from a recording instead of the camera. |
| `holowm run --record FILE [--frames]` | Record the hand tracking while running; `--frames` saves every camera frame too. |
| `holowm panel [--install]` | Open the control panel, or add it to the applications menu. |
| `holowm ctl pause\|resume\|toggle\|debug\|status\|quit` | Control a running instance. |
| `holowm doctor [--no-camera]` | Check that the machine has what HoloWM needs, and measure the tracking rate. |
| `holowm record FILE` | Record hand tracking to a JSONL file. |
| `holowm collect FILE` | Record while prompting one pose after another, so the recording comes labelled. |
| `holowm score FILES…` | Measure how well the poses and gestures in labelled recordings are read. |
| `holowm train FILES…` | Train the optional pose model on labelled recordings. |

## Tuning and measuring

Everything adjustable lives in `~/.config/holowm/config.toml`, in sections for the camera, tracker,
screen mapping, filters, poses, gestures, pie menu, window switcher and overlay. Every key has a
default (`src/holowm/config.py`), and an unknown key is rejected with its name.

Gesture recognition is tuned against recordings rather than by feel:

- `holowm collect` asks for each pose in turn and records when it was held.
- `holowm score` replays those recordings through the same code the live program uses and reports,
  for each pose asked for, what it was read as and which gesture it set off.
- `holowm run --replay` plays any recording back through the full engine and overlay.

`research/label_teacher.py` labels saved camera frames with WiLoR, a slow but more accurate hand
model, to measure where MediaPipe goes wrong when fingers are hidden.
`docs/occlusion-research-plan.md` holds that research and its plan.

## What it needs

- Linux with an X11 session, xfwm4 and a running compositor
- a webcam
- Python 3.12 with MediaPipe, PySide6 (Qt 6), xcffib, evdev and NumPy

Optional, each for one feature: `/dev/uinput` access (smooth scrolling), `pactl` (volume),
`playerctl` (skipping tracks), `v4l2-ctl` (camera settings), and a camera app such as Snapshot or
Cheese (the camera gesture). `holowm doctor` reports which of these are present.

## Where things are

| Path | Contents |
| --- | --- |
| `src/holowm/cli.py` | The `holowm` command and its subcommands |
| `src/holowm/config.py` | Every setting and its default |
| `src/holowm/tracker/` | Camera capture, MediaPipe, the tracker process, recordings and replay |
| `src/holowm/core/` | Hand tracks, filters, poses, face, the engine and its interactions |
| `src/holowm/launcher/` | The pie menu's model and actions, and the camera app |
| `src/holowm/x11/` | The X11 backend, input injection, window pictures, and the fake backend |
| `src/holowm/overlay/` | The overlay process, its bridge to QML, and the QML components |
| `src/holowm/panel/` | The control panel |
| `src/holowm/tools/` | `doctor`, `collect`, `score` and `train` |
| `tests/` | 257 tests, run against synthetic hands, recorded landmarks and the fake backend |
| `research/`, `docs/` | The occlusion research script and plan |

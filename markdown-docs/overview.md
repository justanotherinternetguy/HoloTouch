# HoloTouch: what it does and how it works

HoloTouch lets you control the windows on a Linux desktop with your hands in the air. A webcam watches
your hands, HoloTouch reads what they are doing, and it moves, resizes, closes, scrolls and switches
windows accordingly. A see-through overlay on the screen shows where your hands are and what each
gesture is about to do.

It runs on X11 with the XFCE window manager (xfwm4), and on GNOME under Wayland, on a laptop CPU,
with an ordinary webcam.

## What you can do with it

Each hand is shown on screen as a ring cursor: sky blue for the left hand and coral for the right,
each with a small tag that says L or R. A region in the middle of the camera's view maps to the
whole screen, so the hand never has to reach the edge of the picture.

| Hand shape | What it does | How |
| --- | --- | --- |
| Thumb + index pinch | Move a window | Pinch over a window and carry it. A quick pinch that goes nowhere only brings the window to the front. |
| Second hand pinches too | Resize | While one hand holds a window, the other pinches and the two pull apart or together. |
| Flick a held window | Maximize or minimize | Flick it up and let go to maximize, down to minimize. |
| Hold a window at a screen edge | Send to another workspace | Carry it to the left or right edge and wait; the window and the view move to the next workspace. |
| Point, then tap the thumb down | Left mouse button | Point up with the index finger, thumb held out, to take aim: sights appear round the cursor. Tap the thumb down onto the middle finger to click, twice to double click. Keep it down and move to drag. |
| Thumb + pinky pinch | Pie menu | A ring of items opens at the hand. Move toward one and let go to pick it. |
| Fist, held still over a window | Close the window | A ring fills for about 0.7 s; moving or opening the hand cancels it. |
| Two fingers up | Scroll | Let the two fingers rest leaning toward the screen. Tip them at the screen to scroll down, straighten them up to scroll up: the further, the faster. |
| Claw, turned like a knob | Volume or brightness | Right hand turns the volume, left hand the screen brightness. |
| Open palm, swept to the right | Enter key | A fast sweep to the right presses Enter in whatever has the keyboard. |
| Fist touched to the chin | Window switcher | Every window is laid out as a card with a picture of it. Point at one and pinch to go to it. |
| Letter Y: thumb and pinky out, the rest folded | Dictate | Hold the sign up and speak; a note says it is listening. Let go, and what you said is typed into whatever has the keyboard. |
| "I love you": thumb, index and pinky out | App launcher | Hold the sign up until the launcher appears, then fingerspell an app's name until it is the only one left, or a macro's letters: R, then S, opens Instagram Reels in the browser. |
| Both hands clapped twice | New tab | Only when a web browser has the keyboard: it is sent Ctrl+T. The claps are seen, not heard. |
| Open palm, held still, then tossed straight up | Send the page to the phone | Only when a web browser has the keyboard: the page it shows opens on the Android phone, over Wi-Fi or the cable. |
| Peace sign with both hands | Camera | Held for 1 s, it takes a photo at once: the screen flashes, and the photo is shown for a moment and saved in `Pictures/HoloTouch`. |

The pie menu starts apps (terminal, browser, files), skips music tracks and pauses or plays the music, lists the running windows,
maximizes, minimizes, tiles or closes the window under the hand, and switches workspaces. One of
its items changes with the app that has the keyboard, and holds that app's own keys:

| In | The item is | And holds |
| --- | --- | --- |
| A web browser | This page | Go back and go forward in its history, reload, the next and the previous tab, close the tab, Escape, and send the page to the phone |
| A terminal | This terminal | Copy, paste, a new tab, clear, interrupt (Ctrl+C), the last command, and Escape |
| A file manager | This folder | Go back and go forward, the parent folder, open, copy, paste, and a new tab |
| mpv, Celluloid or VLC | This video | Play or pause, forward and rewind, skip a minute either way, mute, and fullscreen |
| Evince, Atril, Xreader or Papers | This document | The next and the previous page, zoom in and out, fit the width, find, and fullscreen |
| Anything else | This app | Copy, paste, undo, select all, save, find, and Escape |

Each holds seven, the browser's eight, and two that undo each other lie opposite: go back to the
left, go forward to the right. The kinds of app, each told by its window class, and their keys are in
`src/holotouch/launcher/appmenu.py`. The menu's
contents can be replaced with `~/.config/holotouch/menu.toml` (see `contrib/menu.example.toml`).

The launcher opens every app that the applications menu lists, each spelt by its name with the
spaces and digits left out. It lists the apps the letters so far may yet spell, and once only one
is left it opens after a short wait: F, I, R, E, F is enough for Firefox where Firewall is
installed too. Making the sign again takes it all back. J and Z are drawn in the air, which is
not read, so in a name each is spelt by the hand that draws it, held still: that of I for J, and
that of D for Z. `apps = false` under `[spell]` leaves the apps out.

It runs macros as well, listed in `~/.config/holotouch/macros.toml` (see
`contrib/macros.example.toml`): each has its letters, a name, and what it does, which is to open
an address, run a command, start an app, press a key or type some text. Without that file there
is one, RS for Instagram Reels. A macro has to be spelt in full, and J and Z cannot be used in one.

## How it works

HoloTouch is three kinds of process:

1. **The tracker** reads the webcam and finds hands and a face in each frame.
2. **The core** turns those into gestures, acts on windows, and draws the overlay.
3. **The control panel** is an optional window that starts, stops and watches the core.

### 1. Tracker: camera to landmarks

`src/holotouch/tracker/`

- The webcam is read through V4L2 at 1280×720 and 30 frames a second, and each frame is mirrored
  so that moving a hand to the right moves its cursor to the right.
- MediaPipe finds up to four hands per frame and gives 21 landmarks for each, both as positions in
  the picture and as a 3D shape in metres. The core follows two of them; the others are looked for
  so that hands in the background cannot take the user's places. A face mesh is found about 15
  times a second, for the chin gesture and to tell how far off the user is.
- Each result is sent to the core over a pipe as a `FrameSample`, stamped with when the frame was
  captured.
- With no hands in view for 3 s it processes only every second frame, to save power.
- It runs in a process of its own so that model inference never stalls the overlay. The core
  restarts it if it dies or stops sending.

### 2. Core: landmarks to gestures

`src/holotouch/core/`

**Hand tracks** (`hands.py`). Detections are matched to the hands already being followed, so each
hand keeps its identity when hands cross or drop out for a moment. A hand that vanishes is kept for
a quarter of a second before it is forgotten.

Only hands in the foreground are followed. How large a hand is in the picture, set against its
size in metres, tells how far off it is. A hand is left out if it is a room's length away, or if
it is well behind the user's face: at under three quarters of the face's scale, where the user's
own hands measure 0.9 to 2. A hand already followed is kept a little past those limits, so that
it does not come and go. Of the hands that are left, the two nearest are followed: a new hand
takes the place of one being followed only if that one is clearly further off. The limits are
`min_hand_scale` and `behind_face` under `[tracker]`, and the diagnostics panel shows each hand's
size, the least a new hand may be, and the hands left out, drawn faint. A bystander as near the
camera as the user is cannot be told from the user this way.

**Smoothing** (`filters.py`). Positions pass through a 1€ filter, which smooths a slow hand hard
(no jitter) and a fast hand lightly (no lag). The camera gives 30 samples a second and the screen
refreshes faster, so the position is predicted forward between samples from the hand's speed.

**Poses** (`poses.py`). From the landmarks HoloTouch measures a few things in palm lengths: how far
the thumb tip is from each fingertip, how curled and how straight each finger is, how squarely the
palm faces the camera, how far the fingers tilt, and how near the thumb tip is to the middle
finger. Hand-written rules turn these into one of eleven poses: neutral, open, index pinch, pinky
pinch, fist, two fingers, claw, aim (pointing with the thumb held out), press (the thumb
brought down from there), the letter Y and the sign for "I love you". Each pose has separate thresholds for entering and leaving, and must
persist for a short time before it counts, so a pose does not flicker.

**Letters** (`letters.py`). The letters of the manual alphabet are too many and too alike for
rules, so a small network reads them: one hidden layer, fed where each of the hand's joints lies
from the wrist and how far apart they are, in palm lengths. It is asked only while spelling. Many
letters are also gestures (R holds up two fingers, which scroll; S is a fist, which closes a
window), which is why the launcher has a sign that opens it, and nothing else starts until it closes.
The model that comes with HoloTouch was trained on about 1900 public hands of 24 letters;
`holotouch train-letters` adds your own to them.

**Claps** (`claps.py`). A clap is the two palms 14 cm apart or more and then together, within a
third of a second. Hands that meet are often read as one hand or as none, so palms that vanish on
their way together count as having met. Two claps within 0.9 s are acted on.

**Face** (`face.py`). The face mesh gives the chin's position and the face's size, which tell how
near the chin a hand is, and whether it is level with the face or held out in front of it.

**The engine** (`engine.py`, `interactions/`). On every tick the engine looks at each hand's pose
and starts the matching interaction: move, click, pie menu, close, scroll, knob, dictation,
spelling, window switcher or camera. One interaction runs at a time and owns its hands until it ends.

Several guards keep misread hands from doing damage:

- A hand must be in view and relaxed for a moment before its gestures count.
- A pinch that begins while the hand is moving fast is ignored.
- A grab leaves the window alone for the first 150 ms, and a grab shorter than 300 ms is undone.
- The thumb only clicks from a hand that has taken aim, thumb out, for 200 ms. A hand that comes
  to point with its thumb already tucked in is only pointing, and clicks nothing.
- The letter Y has to be held for 300 ms, facing the camera, before the microphone is opened.
- While spelling, only the letters that carry on toward some macro or app are looked for, and
  each has to be held for 400 ms. A hand that looks more like another letter still counts if it
  looks a good deal like the one wanted: R and U are told apart by one crossed finger.
- An app whose name has only been begun is not opened at once, but after 1.2 s with no further
  letter, which leaves time to take it back.
- For 0.7 s after spelling, the hand that spelt starts nothing: its last letter is a fist as
  likely as not.
- A toss has to start from a hand at rest, and rise 0.4 screen heights within 450 ms. A hand
  that is only being raised into view was never at rest, and sends nothing.
- Only application windows can be changed, never the desktop or a panel, and fullscreen windows
  are not grabbed.

A small trained pose model exists as an alternative to the rules (`pose_model.py`, `holotouch train`).
It is off by default and the rules are what HoloTouch uses.

### 3. Acting on the desktop

`src/holotouch/x11/`, `src/holotouch/gnome/`

The engine talks to a `WindowBackend` interface (`core/actions.py`), which has three implementations.
`session.py` picks the one for the desktop HoloTouch is started on:

- **`X11Backend`** keeps a cached model of xfwm4's windows, updated from X events, and changes them
  with standard EWMH requests: move, resize, maximize, minimize, close, activate, switch workspace.
  Clicks and key presses go through XTEST. Scrolling uses a virtual mouse on `/dev/uinput` for
  smooth high-resolution wheel events, and falls back to XTEST steps. Volume is set with `pactl`,
  brightness through `/sys/class/backlight`, and tracks are skipped and the music paused with `playerctl`.
  Dictated text is typed with `xdotool`.
- **`GnomeBackend`** is for GNOME under Wayland, where no program but the compositor may list
  windows, move them, press keys or read the clipboard. All of that is asked of a GNOME Shell
  extension of HoloTouch's own (`gnome/extension/`), over the session bus. The extension sends the
  state of the desktop whenever it changes, moves and resizes windows as Mutter itself would,
  clicks, scrolls and presses keys through GNOME Shell's virtual pointer and keyboard (the ones its
  on-screen keyboard uses), hands dictated text to a text field as an input method does, and makes
  the window switcher's pictures. It watches nothing until HoloTouch is running, and stops when
  HoloTouch has gone. `holotouch gnome` installs it; GNOME Shell has to be started again, by
  logging out and back in, before it finds it. The volume, the brightness and the music are
  reached as on X11.
- **`FakeBackend`** holds windows in memory only. Tests use it, and so does practice mode
  (`--dry-run`), where gestures act on two stand-in windows.

**Macros** (`launcher/macros.py`) are read from `macros.toml`, and the one that was spelt is run:
an address is handed to `xdg-open`, a command to the shell, an app to `gtk-launch`, and a key or
text to the backend.

**Apps** (`launcher/apps.py`) are found when HoloTouch starts, from the desktop files in the XDG
data directories: those the applications menu would list on this desktop, and whose program is
installed. Each is opened with `gtk-launch`. Of two that are spelt alike only the first is kept,
and a macro comes before an app.

**The phone** (`launcher/phone.py`) is sent a page by whoever runs the engine, which only says
when an open palm was tossed upward at a web browser. A browser tells no other program which
page it shows, so the address is taken as a person would take it: Ctrl+L and Ctrl+C are pressed
in the browser, the clipboard is read with `xclip` (on GNOME, through the Shell extension), and
Escape and Shift+F6 hand the keyboard back to the page. What the clipboard held is put back if it was text. Then `adb` tells the
phone to open the address: any Android phone with USB debugging allowed, which needs no app of
its own. There is no server, and nothing leaves the local network.

Plugged in, the phone is reached by USB. `holotouch phone`, run once while it is plugged in,
has it listen for adb on the network as well and keeps its address in
`~/.config/holotouch/phone`; from then on pages go over Wi-Fi and the cable can come out. The
computer and the phone have to be on the same network, and one that lets them talk. The phone
listens until it is next restarted, and the network may give it another address: run
`holotouch phone` again then. A phone that cannot be reached over Wi-Fi is sent the page by USB
if it is plugged in. `holotouch phone --usb` goes back to the cable alone. While it listens,
anything on the network can ask the phone for debugging access, and the phone asks whether to
allow it: allow only this computer.

By default the address opens in the phone's browser. Under `[phone]`,
`action = "share"` hands it to the phone's share sheet instead, to pick the app that keeps it,
`app` names the one app that gets it, `serial` names the phone when it is not the one
`holotouch phone` found or the only one plugged in, and
`enabled = false` turns the gesture off. The overlay says whether the page was sent, and
`holotouch ctl phone` sends it with no hand at all. Which pages were sent is not logged.

**The photo** (`launcher/camera.py`) is taken by HoloTouch itself, from the camera it is
watching the hands with. The core asks the tracker process for it, and the frame the tracker
has in hand is saved as a JPEG, turned back from the mirror the tracker is shown: on a laptop,
within a twentieth of a second of the ring completing. Nothing is opened and tracking goes on.
The photo is the size under `[camera]`, 1280×720 unless changed, which may be less than the
webcam's largest. `camera_dir` under `[gesture]` says where photos go, and `camera_hold_ms` how
long the sign is held. Naming a camera app as `camera_command` (`"snapshot"`) has that app
opened instead and its shutter key pressed once its window has been up for `camera_shutter_ms`:
at the webcam's full size and with a look at the picture first, but seconds later, and with
tracking paused until the app is closed, since only one program can use the webcam.

**Dictation** (`launcher/dictate.py`) is done by whoever runs the engine, which only says when the
letter Y is held. While it is, the microphone is recorded by `parecord` (or `arecord`) to a file
in the runtime directory. When the sign is dropped, the recording is handed to a speech-to-text
program, and the text it prints is typed into the window that has the keyboard. By default that
program is [Handy](https://handy.computer) run headless (`handy --transcribe-file`), which works on
this machine alone; `dictate_command` under `[gesture]` names another. Recordings are deleted as
soon as they have been read, and what was said is not logged.

### 4. The overlay

`src/holotouch/overlay/`

A fullscreen, transparent, click-through window drawn with Qt Quick sits above everything. The
engine produces an `OverlayState` each tick and a bridge hands it to QML, which draws:

- a ring cursor for each hand, in that hand's colour, which tightens as the pinch closes. A hand
  taking aim gets sights round its ring; one that has not moved for a while goes small and pale;
  one not yet trusted is dashed; one that is lost while holding something leaves a hollow ghost
  and a note
- an outline just outside the window under the hand. A held window gets a solid frame in the
  holding hand's colour, with a bead on its nearest edge; one being resized gets a grip at the
  corner nearest each hand, the size on its bottom edge, and the outline it began with
- the pie menu: petals around a seed, with the wedge being aimed at shaded, since only the
  direction of the hand counts
- the window switcher: every window's picture as a card, over a dimmed desktop
- a ring for closing a window, as wide as the fist may drift, and one for the camera sign; then
  a flash, and the photo that was taken, shown as a print for a moment
- the volume or brightness dial, with its number; a click pulse; a bar at the screen edge that
  fills while a held window waits to cross to the next workspace
- the launcher: the letters taken so far, the one the hand is making as the model reads it, a
  tile that fills as a letter is held, and under them the first six apps and macros still within
  reach, each with its icon or its letters and with what has been spelt of it picked out. The
  one about to be opened fills up as it waits. Then a note of what was opened
- brief notes for the workspace switched to, the track skipped, the Enter key pressed, the tab opened and the page sent
  to the phone (or why it could not be), and one that says the
  microphone is listening, then that what was said is being written
- one instruction at a time, for a prompted recording or for practice mode
- an optional diagnostics panel showing frame rate, latency, each hand's pose and measurements,
  and the hands and face as the camera sees them, with the hands left out as background drawn faint

On GNOME the overlay is the same X11 window, shown by XWayland: Wayland itself has no window that
may sit above the others and let clicks through. It stops a few pixels short of the bottom of the
screen, because GNOME hides its top bar under a window that covers a whole monitor. On a scaled
monitor XWayland gives X11 programs a larger screen than the monitor has pixels and scales the
result down, so HoloTouch draws that much larger (`session.pixel_ratio`), and converts between
the overlay's pixels and GNOME's own units wherever it talks to the extension.

Everything pairs cream with ink so that it reads over light and dark windows alike, and nothing
samples or blurs the desktop. The colours and typefaces are in `src/holotouch/theme.py`, shared with
the control panel.

The core also has a tray icon (pause, diagnostics, quit) and a control socket.

### 5. The control panel

`src/holotouch/panel/`

`holotouch panel` opens a window from which HoloTouch is started and stopped without a terminal.
`holotouch panel --install` adds it to the applications menu. It shows:

- a Start/Stop dial whose ring is the state, and that state in a word and a sentence: running,
  paused, stopped, practising, or running with no camera
- the number of hands in view, the gesture in progress and the frame rate
- a button to pause and resume tracking, and the switch for practice mode
- a guide to the gestures, each with an illustrated hand playing it
- practice: four steps on the two stand-in windows (grab, move, resize, pie menu), one at a
  time, each shown on the desktop as well and ticked off when HoloTouch sees it done
- the results of the machine checks, in plain words, with what to do about any that is not fine
- a drawer with the switch for the diagnostics view and HoloTouch's log, which opens by itself when
  something goes wrong

The panel starts HoloTouch as a separate process and follows it over the control socket, so closing
the panel leaves HoloTouch running, and a HoloTouch started from a terminal is picked up as well.

## Commands

| Command | What it does |
| --- | --- |
| `holotouch run` | Start tracking and the overlay. This is the default with no command. |
| `holotouch run --debug` | The same, with the diagnostics panel shown. |
| `holotouch run --dry-run` | Act on stand-in windows instead of real ones. |
| `holotouch run --replay FILE [--loop]` | Drive the engine from a recording instead of the camera. |
| `holotouch run --record FILE [--frames]` | Record the hand tracking while running; `--frames` saves every camera frame too. |
| `holotouch panel [--install]` | Open the control panel, or add it to the applications menu. |
| `holotouch ctl pause\|resume\|toggle\|debug\|status\|phone\|quit` | Control a running instance. `phone` sends the page in the browser to the phone, as the toss does. |
| `holotouch phone [--usb]` | Let the Android phone that is plugged in be sent pages over Wi-Fi from now on; `--usb` goes back to the cable. |
| `holotouch gnome [--remove]` | Install the GNOME Shell extension that HoloTouch needs on GNOME under Wayland, or take it out. Log out and back in afterwards. |
| `holotouch doctor [--no-camera]` | Check that the machine has what HoloTouch needs, and measure the tracking rate. |
| `holotouch record FILE` | Record hand tracking to a JSONL file. |
| `holotouch collect FILE` | Record while prompting one pose after another, so the recording comes labelled. |
| `holotouch collect FILE --letters` | The same, asking for the letters of the manual alphabet and a resting hand. |
| `holotouch train-letters FILES…` | Train the model that reads spelt letters on those recordings, added to the public hands. |
| `holotouch score FILES…` | Measure how well the poses and gestures in labelled recordings are read. |
| `holotouch train FILES…` | Train the optional pose model on labelled recordings. |

## Tuning and measuring

Everything adjustable lives in `~/.config/holotouch/config.toml`, in sections for the camera, tracker,
screen mapping, filters, poses, gestures, spelling, the phone, pie menu, window switcher and overlay. Every key has a
default (`src/holotouch/config.py`), and an unknown key is rejected with its name.

Gesture recognition is tuned against recordings rather than by feel:

- `holotouch collect` asks for each pose in turn and records when it was held.
- `holotouch score` replays those recordings through the same code the live program uses and reports,
  for each pose asked for, what it was read as and which gesture it set off.
- `holotouch run --replay` plays any recording back through the full engine and overlay.

The model that reads letters is made and measured the same way. `research/letters_public.py`
trains the one HoloTouch comes with on ASLNow!'s public landmarks (MIT licence), and tests it on
hands held out of training: it reads 98% of them right, though with the same people on both
sides of the split, so expect less on a new hand. `holotouch collect FILE --letters` records your
own, about two minutes a round, and `holotouch train-letters FILE` adds them to the public ones,
reports how the result reads holds it was not trained on, and saves it to
`~/.config/holotouch/letters.npz`, which is then used. Your own recording also shows the model a
resting hand, which the public data has none of: without it every hand looks like some letter.

`research/label_teacher.py` labels saved camera frames with WiLoR, a slow but more accurate hand
model, to measure where MediaPipe goes wrong when fingers are hidden.
`docs/occlusion-research-plan.md` holds that research and its plan.

## What it needs

- Linux with an X11 session, xfwm4 and a running compositor; or GNOME 45 to 51 under Wayland (tried on GNOME 51),
  with XWayland, and HoloTouch's Shell extension (`holotouch gnome`, then log out and back in)
- a webcam
- Python 3.12 with MediaPipe, PySide6 (Qt 6), xcffib, evdev, jeepney and NumPy

Optional, each for one feature: `/dev/uinput` access (smooth scrolling), `pactl` (volume),
`playerctl` (skipping tracks and pausing the music), `v4l2-ctl` (camera settings), a camera app such as Snapshot or
Cheese (only where one is named as `camera_command`), `parecord`, `xdotool` and Handy (dictation), `gtk-launch` (the launcher's apps), `xdg-open` (macros that open an address), and `adb`, `xclip` and an Android phone with USB debugging allowed (sending a page to the phone). On GNOME, `/dev/uinput`, `xdotool` and `xclip` are not needed: the Shell extension scrolls, types and reads the clipboard. `holotouch doctor` reports which of these are present.

## Where things are

| Path | Contents |
| --- | --- |
| `src/holotouch/cli.py` | The `holotouch` command and its subcommands |
| `src/holotouch/config.py` | Every setting and its default |
| `src/holotouch/tracker/` | Camera capture, MediaPipe, the tracker process, recordings and replay |
| `src/holotouch/core/` | Hand tracks, filters, poses, letters, face, the engine and its interactions |
| `src/holotouch/launcher/` | The pie menu's model and actions, the keys it holds for each kind of app, the macros, the installed apps, the photo and the camera app, dictation, and the phone |
| `src/holotouch/x11/` | The X11 backend, input injection, window pictures, and the fake backend |
| `src/holotouch/gnome/` | The backend for GNOME under Wayland, the GNOME Shell extension it talks to, and what installs it |
| `src/holotouch/session.py`, `system.py`, `keys.py` | Which desktop this is and what follows from it; the volume, brightness and music; keys by name |
| `src/holotouch/overlay/` | The overlay process, its bridge to QML, and the QML components |
| `src/holotouch/panel/` | The control panel |
| `src/holotouch/theme.py`, `ui/`, `fonts/` | Colours and typefaces, the icons both windows draw, and the bundled fonts (Open Font License) |
| `src/holotouch/tools/` | `doctor`, `collect`, `score`, `train` and `train-letters` |
| `tests/` | 456 tests, run against synthetic hands, recorded landmarks, the fake backend, and private xfwm4 and GNOME Shell sessions |
| `research/`, `docs/` | The occlusion research script and plan, and the script that trains the letter model |

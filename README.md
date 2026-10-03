# HoloWM

Spatial hand-gesture window control for XFCE on X11. A webcam tracks your hands and face; a pinch grabs whatever
window is under your hand, anywhere on its surface, and the window follows. No mouse cursor is involved:
HoloWM talks to the window manager directly.

## Gestures

| Gesture | Action |
|---|---|
| Open hand in view | A ring cursor follows the hand; the window under it is outlined |
| Thumb + index pinch, hold, move | Grab the window under the hand and move it |
| Second hand pinches during a grab | Resize: pull the hands apart or together; the midpoint moves the window |
| Release a grab with a downward flick | Minimize |
| Release a grab with an upward flick | Maximize |
| Hold a grabbed window against the left/right screen edge | Carry it to the next workspace |
| Closed fist held still over a window (0.7 s) | Close it. A ring fills first; open the hand to cancel |
| Fast open-palm swipe left/right | Switch workspace |
| Fist touched to the chin | Open the window switcher. Pinch a card to go to that window |
| Thumb + middle finger pinch | The left mouse button, held down while they touch: a quick pinch clicks, two double-click, a carried one drags |
| Thumb + pinky pinch | Open the pie launcher. Move toward an item, release to launch |
| Index + middle finger extended, tilt them down or up | Scroll the window under the hand; open the hand to stop |
| Both hands hold up two fingers, the peace sign, for 3 s | Open the camera app and take a photo. A ring fills first; open a hand to cancel |
| Right-hand claw, as if gripping a knob, turned in place | Volume: clockwise turns it up; open the hand to let go |
| Left-hand claw, turned the same way | Screen brightness |

In the pie launcher, moving a full stroke onto an item with a dot enters its submenu; the small `‹` item
goes back. Releasing in the centre cancels.

The window switcher is HoloWM's own Alt+Tab: a panel of cards, one per window, most recently used first.
It lists every workspace and minimized windows too, with a picture of each window that is on screen and
the icon of each one that is not. To open it, rest a closed hand against your chin for a quarter of a
second. The window you used before the current one starts highlighted, so taking the hand away and
pinching goes straight back to it. Point at another card to highlight it instead, then pinch to switch;
HoloWM changes workspace or un-minimizes as needed. To dismiss the switcher, touch your chin again, pinch
with nothing highlighted, or take your hands out of view.

The chin touch needs your face in view. HoloWM tells a fist on the chin from one that merely passes in
front of it by size: a hand level with the face looks smaller than one held out toward the camera. A fist
that might be either does nothing at all, so a fist in front of your chin has to be held well forward to
close the window under it.

A quick pinch on a window that goes nowhere only brings it to the front, and a maximized window
stays put under a pinch until you drag it. Flick a window up to maximize it and drag it free to
restore it; the pie launcher's Window item does both too.

The pie launcher's Music item skips tracks: enter it, then move right for the next track or left for
the one before, and release. A pill at the bottom of the screen says which way it went. Tracks are
skipped through `playerctl`, which acts on whichever player was last in use (anything that speaks
MPRIS: Spotify, a browser, VLC, mpv with its plugin). Without it the two items do nothing.

Scrolling works like a throttle, with the hand held still. Wherever the two fingers settle in the
first third of a second after you make the pose counts as rest. Tip them forward and down from there
to scroll down, lean them back to scroll up; the further they tilt, the faster it goes, and holding a
tilt keeps scrolling. Opening the hand stops it.

Tipped right down, the two fingers lie over the rest of the hand and the camera can no longer tell
what the hand is doing: it reads as a pinch or a fist as often as not. So while the fingers read as
pointing at the camera or lower, HoloWM keeps scrolling down at full speed whatever the hand looks
like, and grabs or closes nothing. Bring the fingers back up, or open the hand, to stop. A real fist
stops it too, since its index finger is curled right up; the fist then has to be made again before it
closes a window.

To click something on screen, put the hand's cursor on it and touch thumb to middle finger, with
the other fingers up and the palm to the camera. That is the left mouse button: it goes down where
the cursor is as the two touch and comes up when they part. So a quick pinch is a click, two are a
double click, and a pinch that is held and carried drags whatever is under it: a selection, a slider,
a scrollbar, a window by its title bar. A ripple shows where the button went down. It works anywhere
on the screen, and has nothing to do with the thumb and index pinch that grabs windows.

A hand held still wanders by a few dozen pixels, which is more than enough to turn a click into a
drag. So the pointer stays exactly where the button went down until the hand has moved 3% of the
screen height (`click_slop`), and only then follows it. For the same reason a second pinch within a
second, at very nearly the same place, lands on the same pixel as the first, so that double clicks
register. How quick the two have to be is your desktop's double-click time. The mouse pointer goes
where the click is and stays there afterwards, as it would after a click with a mouse.

The pinch is read from the hand's shape alone, and only when the palm faces the camera. The ring
finger and pinky have to stay up: with them folded away it is a hand pointing with one finger, whose
thumb rests on the middle finger too, and that does nothing.

To take a photo, hold up two fingers on both hands, a peace sign with each, and keep them there
for three seconds while the ring between your hands fills. Opening either hand cancels it. It takes
both hands because one hand held that way is the scroll gesture, and nothing in the hand tells a peace
sign from it. If one hand is already scrolling, raising the other the same way stops the scroll and
starts the ring.

Only one program can use the webcam at a time, so HoloWM gives it up as the app opens: tracking pauses,
the overlay goes, and no gesture works until the app is closed, which has to be done with the mouse or
keyboard. Tracking then starts again by itself. Resuming by hand (`holowm ctl resume`, or the tray
icon) while the app is still open takes the webcam back as soon as the app lets go of it. The app is
the first installed of `snapshot`, `cheese`, `kamoso` and `guvcview`, or whatever `camera_command`
names.

The photo is taken by the app, three seconds after its window appears, which is time enough to pose
again. Camera apps cannot be asked for a photo from outside, so HoloWM presses the app's shutter key
for you: `t`, which is Snapshot's (set `camera_shutter_key` for another app, or to nothing to only open
it). The key is pressed only while the app's window has the keyboard, so it is never typed into
anything else; if the window cannot be given the keyboard, no photo is taken. Snapshot saves its
photos in `Camera` under your pictures folder, and applies its own countdown if you have set one. With
`--dry-run` the app opens but no key is pressed.

A knob is gripped by bending all your fingers as if round a real one, thumb clear of them, and holding
that for a third of a second; a ring showing the level appears round your hand. The right hand's knob
is the sound volume and the left hand's the screen brightness. Turn the hand clockwise to raise it and
anticlockwise to lower it: a third of a turn covers the whole range. Open or close the hand to let go.
Letting go turns the hand a little, so the level returns to where it stood a quarter of a second
before. Brightness stops at 5%, so the screen can always be seen to turn it back up.

The volume is set through `pactl`, so PulseAudio or PipeWire's PulseAudio layer is needed. The
brightness is written to the backlight under `/sys/class/backlight`, which a laptop has and which your
user must be allowed to write; where it cannot be read, the left-hand claw does nothing.

Tracking is always live. To guard against accidents, a hand has to be in view and open for a moment
before its gestures count, pinches made while the hand is moving fast are ignored, and one gesture owns
the hands at a time. A hand turned away from the camera is read less surely, so its pinch counts only
if the hand is nearly still as it is made.

A grab does nothing to the window for the first 0.15 s of the pinch; the window then catches up with
the hand. A grab that is over within 0.3 s is undone: the window goes back where it was, to maximized
if it was, and the window in use before is in use again. A waving or scratching hand is misread as
pinching for about that long, and this keeps it from throwing windows about. The cost is that a real
drag has to last longer than 0.3 s to count. A quick pinch in place, which brings the window to the
front, is not undone.

`holowm ctl toggle` (or a click on the tray icon) pauses everything and removes the
overlay.

## Requirements

- XFCE with xfwm4 on X11, with the compositor enabled
- A webcam (developed against a 1280x720, 30 fps laptop camera)
- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- Optional: write access to `/dev/uinput` (the `input` group) for smooth scrolling
- Optional: a camera app (Snapshot, Cheese, Kamoso or guvcview) for the two-handed peace sign
- Optional: `playerctl`, for the pie launcher's Music items that skip tracks

## Install and run

```sh
uv sync
uv run holowm doctor      # checks the session, camera, and tracking speed
uv run holowm run         # start; add --debug for the tracking diagnostics panel
```

The hand and face models (about 12 MB together) are downloaded to `~/.cache/holowm/` on first run. On
start HoloWM turns off the camera's low-light frame-rate halving and sets its anti-flicker frequency (see
`[camera]` below).

Other commands:

```sh
uv run holowm run --dry-run          # gestures act on two stand-in windows, not real ones
uv run holowm ctl pause|resume|toggle|debug|status|quit
uv run holowm record session.jsonl   # record 15 s of hand tracking
uv run holowm record session.jsonl --frames   # the same, and every camera picture in session.frames/
uv run holowm run --record session.jsonl      # record while HoloWM runs, until you quit; takes --frames too
uv run holowm run --replay session.jsonl --dry-run
```

To start with the desktop, copy `contrib/holowm.desktop` to `~/.config/autostart/` and make sure `holowm`
is on your `PATH` (for example `uv tool install .`).

## Configuration

Everything has a default; override what you need in `~/.config/holowm/config.toml`. All keys are in
`src/holowm/config.py`. The ones most worth knowing:

```toml
[camera]
device = "/dev/video0"
power_line_hz = 60        # 50 in most of Europe/Asia
fix_controls = true       # set false to leave camera settings untouched

[tracker]
face = true               # false turns face tracking, and with it the chin gesture, off

[mapping]                 # the part of the camera frame that maps to the whole screen
box_x = 0.15
box_y = 0.20
box_w = 0.70
box_h = 0.60

[pose]
pinch_enter = 0.25        # lower = fingers must be closer to count as a pinch
pinch_exit = 0.42
claw_min = 0.58           # the knob claw: every finger's straightness must lie between these two
claw_max = 0.86           # (a relaxed hand measures 0.91 and up, a fist 0.6 and under)
claw_thumb = 0.38         # and the thumb must be this far clear of every fingertip, in palm lengths
max_onset_speed = 2.5     # a pinch made by a hand moving faster than this is ignored (screen heights/s)
turned_facing = 0.73      # a hand turned further from the camera than this (1 = facing it, 0 = side-on)...
turned_onset_speed = 0.6  # ...has to be slower than this for its pinch to count

[filter]                  # smoothing; see Tuning below
min_cutoff = 1.5          # hand position: lower = steadier when slow or still
beta = 12.0               # hand position: higher = less lag when fast
landmark_min_cutoff = 4.0 # the same pair for the fingers, which poses and pinches are read from
landmark_beta = 60.0
tilt_min_cutoff = 1.0     # and for the finger tilt that sets the scroll speed
tilt_beta = 0.03

[gesture]
flick_speed = 2.0         # screen heights per second needed to minimize/maximize
close_dwell_ms = 700
swipe_min_travel = 0.30   # screen widths
chin_reach = 0.3          # how near the chin the fist must come, in face heights
chin_depth = 1.5          # how much nearer the camera than the face the fist may look; raise if touches are missed
chin_hold_ms = 250        # how long the fist must rest there
swipe_natural = true      # hand left -> next workspace
click_slop = 0.03         # screen heights the hand may wander with the mouse button down before it drags
grab_confirm_ms = 150     # how long a pinch must last before the window follows the hand
grab_undo_ms = 300        # a grab over within this long is undone; 0 turns that off
scroll_speed = 20         # top scroll speed, wheel notches per second
scroll_dead_deg = 8       # finger tilt below this does not scroll; raise it if scrolling creeps
scroll_full_deg = 40      # finger tilt that gives the top speed
scroll_invert = false     # true: tilting the fingers down scrolls up
camera_hold_ms = 3000     # how long both hands must hold up two fingers to open the camera app
camera_command = ""       # the app to open, as a shell command; empty picks the first one installed
camera_shutter_key = "t"  # the key that takes a photo in that app; "" only opens it
camera_shutter_ms = 3000  # how long after the app's window appears the key is pressed
knob_dead_deg = 8         # a turn of the claw smaller than this changes nothing
knob_full_deg = 120       # the turn that takes the volume, or the brightness, from nothing to full
knob_invert = false       # true: turning clockwise turns it down
wrap_workspaces = false

[switcher]
all_workspaces = true     # false lists only the current workspace
thumbnails = true         # false shows icons only
columns = 6               # most cards in one row

[ui]
scale = 1.6               # overlay element size
accent = "#00e5ff"
```

The pie menu defaults to Terminal, Browser, Files, Music (next and previous track), running windows,
window actions and workspaces. To define your own, copy `contrib/menu.example.toml` to
`~/.config/holowm/menu.toml`.

### Tuning

Run with `--debug` to see, per hand, the recognised pose, the pinch distances (`i` for index, `m` for
middle, `p` for pinky; a value below `pinch_enter` counts as a pinch) and `t`, the tilt of the index and middle fingers
in degrees, which is what scrolling follows. The panel also shows your hands inside the camera frame with
the dashed box that maps to the screen: if you have to reach uncomfortably far, shrink or move the box.

The index pinch is measured two ways and the smaller is used: between the fingertips in MediaPipe's
metric landmarks, and between them as the picture shows them. The metric landmarks alone put touching
fingertips up to most of a palm apart when the palm faces the camera or the hand is side-on.

The same panel outlines your face and draws a circle around your chin; a fist has to reach into that
circle. The `face` line gives two numbers per hand: `c`, its distance from the chin in face heights
(a touch needs less than `chin_reach`), and `z`, how much nearer the camera it looks than your face
(a touch needs less than `chin_depth`). If touching your chin does nothing, read `z` while you do it
and set `chin_depth` a little above it.

Jitter is removed by [1€ filters](https://gery.casiez.net/1euro/) on the hand position, the finger
landmarks and the scroll tilt. Each has a `min_cutoff` and a `beta` under `[filter]`, tuned the way that
page describes: set `beta` to 0 and lower `min_cutoff` until a still or slowly moving hand stops
jittering, then raise `beta` until fast movement stops lagging. The three `beta` values are on different
scales (screen heights, metres and degrees), so they cannot be compared with each other.

`uv run holowm -v run` also prints what each gesture did (grabs, taps, flicks, the mouse button), which
helps when a gesture does something you did not intend.

If moved windows leave copies of themselves behind on an empty workspace, the desktop background window
has been minimized; `uv run holowm doctor --no-camera` reports that and prints the command to restore it.

## How it works

```
tracker process                      core process (Qt event loop)
  camera (V4L2 MJPG, 30 fps)           hand association, One Euro filter, prediction to "now"
  MediaPipe hand landmarks,     ->     pose classifier -> interaction engine
  face landmarks (15 a second)
                                       -> EWMH requests to xfwm4, and the overlay state
                                       overlay: transparent, click-through Qt Quick window
```

- `tracker/` runs in its own process so inference never stalls the interaction loop, and is restarted if
  it dies.
- `core/` is pure logic: smoothing and prediction (`filters.py`), hand identity and screen mapping
  (`hands.py`), poses (`poses.py`), the face (`face.py`), and one class per gesture under `interactions/`. It drives a
  `WindowBackend` protocol, so it runs the same against X11 or the in-memory fake.
- `x11/` is the real backend: a cached model of xfwm4's windows and EWMH client messages.
- `overlay/` draws the cursors, outlines, pie menu, window switcher and HUD.

## Measuring how well poses are read

```sh
uv run holowm collect recordings/ada-right-1.jsonl --person ada --frames
uv run holowm score recordings/ada-*.jsonl
```

`collect` asks for one pose after another on screen: two seconds to get ready, then three to hold it
while a bar fills. A round is thirteen poses and takes about a minute; two rounds are the default
(`--rounds N`). Your hands are tracked and shown but start no gestures, so nothing on the desktop is
touched. Beside the recording it writes `ada-right-1.labels.json`: which pose was held when, and whose
hand it was. Ctrl-C stops early and keeps the poses finished so far.

`score` reads those recordings the way the running program does and prints two tables. The first
shows what the frames of each prompted pose were read as, and the share read right. The second plays
each recording through HoloWM over a stand-in window and shows whether the gesture that pose should
set off ran, for how much of the hold it was kept up, and what else ran instead. Given recordings from
several people it also gives each person's share.

### Training a model on those recordings

```sh
uv run holowm train recordings/*.jsonl
```

This fits a small network that reads the pose from the distances between the hand's joints, in place
of the hand-written rules. With more than one recording it first prints the benchmark twice: for the
rules, and for the model with each recording read by a model trained on the others, so that it is
tested on a recording it has not seen. It then saves a model trained on everything and says which line
of `config.toml` (`[pose] model = ...`) turns it on. Nothing uses the model until that line is set;
`holowm score --model FILE` scores with one.

A pose held still for three seconds is one example of it, however many frames it fills, so the model
needs many holds of each pose, moved and turned while they are held. On two sessions (four holds a
pose) it did no better than the rules: as many holds right, with pinches kept up less well.

## Recording pictures for a better model

MediaPipe gives a confident position for a fingertip it cannot see, and HoloWM acts on it.
`docs/occlusion-research-plan.md` describes a way to correct that: train a small model on what a
slower, more accurate one (WiLoR, the "teacher") says about the same pictures. The first steps exist:

```sh
uv run holowm run --dry-run --debug --record recordings/edge-on.jsonl --frames
uv run research/label_teacher.py recordings/edge-on.jsonl --every 10 --overlay
```

The first command records while HoloWM runs, so you see what it makes of your hands as you go: the
cursors, and in the debug panel the hands in the camera frame, the pose read from each and the gesture
in progress. With `--dry-run` nothing you do reaches a real window. Ctrl-C ends the recording.
`holowm record FILE --frames --seconds N` records the same things for a fixed time and shows nothing.

`--frames` saves every camera picture in `recordings/edge-on.frames/`, mirrored as the tracker saw
it, including the pictures tracking skips while no hands are in view. Each is named by its capture time
in microseconds, which is `t_capture` in the recording, so landmarks and pictures match exactly.
Expect about 300 MB a minute. A name whose pictures already exist is refused.

`label_teacher.py` runs WiLoR over those pictures and writes `recordings/edge-on.teacher.jsonl`: one
line per picture, with each hand's handedness, detector confidence, box, 21 points in the picture and
21 in metres. Handedness, joint order and axes are the same as in the recording. With `--overlay` it
also draws every labelled picture in `recordings/edge-on.overlay/`, WiLoR's hands in green over
MediaPipe's in red, which is how to judge whether the teacher is right where MediaPipe is wrong.

The script runs in an environment of its own, which uv builds on first use, and downloads 2.6 GB of
weights to `~/.cache/holowm/wilor/`. On an 8-core laptop CPU it takes about 0.8 s a picture with one
hand in view, so use `--every N` or `--limit N` for a first look; a run that is stopped carries on
where it left off. WiLoR's weights are licensed for non-commercial use only (CC BY-NC-ND).

## Tests

```sh
uv run pytest
```

The suite drives the engine with synthetic hands against the fake backend, checks pose classification
and the chin touch on landmarks the real models produced for photos, and runs the X11 backend against a private
Xvfb display with its own xfwm4 (skipped if those are not installed). The scroll gesture is also run on
landmarks recorded from real steep tilts, and the labelling script with a stand-in for WiLoR. It never
touches your session or your camera.

## Limits

- The camera's 30 fps sets the floor on latency; motion between frames is predicted.
- xfwm4's edge tiling does not apply to hand drags; use the pie menu's tile actions.
- Depth from a single camera is unreliable, so there are no push/pull gestures.
- The cursor follows the whole hand, so a click lands to within a button, not a pixel: small
  targets take a steady hand.
- If HoloWM is killed outright while a pinch holds the mouse button down, the button stays down
  until the next real click.
- While the camera app opened by the peace sign is running, HoloWM has no webcam and tracks nothing.
- Resting your chin on your fist is the switcher gesture whether you mean it or not. Touch the chin again
  to put the switcher away, or set `face = false` under `[tracker]` to turn the gesture off (the pie
  menu's window list still switches windows).
- The switcher is drawn by HoloWM; it is not xfwm4's Alt+Tab popup and does not follow its settings.
  Window pictures need the compositor. A window that is minimized or on another workspace shows its
  icon, or the picture from the last time the switcher was open while it was on screen.
- Over a fullscreen game or video the overlay may not be drawn, because xfwm4 can bypass compositing
  for fullscreen windows. Pausing HoloWM hides the overlay window entirely.

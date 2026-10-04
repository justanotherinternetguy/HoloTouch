# Improving hand tracking under occlusion: research review and plan

Written 2026-10-03. This document records a literature review, an assessment of which research can
help HoloTouch, and a step-by-step plan for training a small occlusion-aware model by distilling a
large offline one. Recording and labelling (Phases 1 and 3) now have code; see Status.

## Summary

- HoloTouch tracks hands with MediaPipe on a laptop CPU. Its main accuracy problem is occlusion: when a
  fingertip is hidden, MediaPipe still reports a confident position, and the engine acts on it.
- None of the state-of-the-art occlusion-robust models can replace MediaPipe live on this machine.
  They need a discrete GPU, use future frames, or have no released weights.
- The plan is to use one of those models as an offline "teacher": label recorded webcam footage with
  it, then train a tiny "student" network that runs after MediaPipe, sees only past frames, and
  outputs corrected landmarks plus a per-joint uncertainty.
- The realistic gain is fewer dropped grabs and fewer false pinches during brief occlusions. It will
  not improve millimetre accuracy across the board.
- The first four phases of the plan (record, collect, label, clean) are worth doing even if no
  student is ever trained, because they measure exactly where and how often tracking fails today.

## Status

Updated 2026-10-03. No footage has been recorded with the real camera yet. Every number here comes
from ten photos played through the real tracker in place of the camera (400 pictures, of which 100
were labelled).

- **Phase 1 is built.** `holotouch record FILE.jsonl --frames` saves every camera picture in
  `FILE.frames/`, named by capture time in microseconds. All 364 landmark frames of the test
  recording matched a picture, tracking stayed at 30 fps and 19 ms, and stopping with Ctrl-C lost
  nothing. `holotouch run --record FILE.jsonl --frames` records the same while HoloTouch runs, which is
  how to record the natural sessions of Phase 2 and to see the hands and gestures while recording.
- **Phase 3 is built up to the go/no-go check.** `research/label_teacher.py` runs WiLoR-mini with
  its own detector over a recording's pictures, writes `FILE.teacher.jsonl`, resumes a stopped run,
  and with `--overlay` draws both models' hands on each picture for inspection.
- **Speed on this CPU:** 0.06 s a picture to find hands plus 0.54 s for each hand found on the
  photos (float32, 8 threads), and 0.77 s a picture on real footage with one hand in view. Thirty
  minutes of footage is then about 12 hours; with `--every 3`, about 4. Two minutes at `--every 10`
  takes about 5 minutes, so the first go/no-go check can be done locally and nothing has to be
  uploaded.
- **Handedness needs no conversion.** Phase 3 step 6 expected an inversion and was wrong. MediaPipe
  names a hand by how it looks in the picture it is given: its own `right_hands.jpg` sample reads
  "Right" as photographed and "Left" when mirrored. WiLoR does the same, and the two agreed on all 84
  matched hands. On HoloTouch's mirrored frames both therefore name the user's other hand.
- **Joint order matches** (step 7): matched joint for joint, the two models' points lie 0.06 to 0.14
  palm lengths apart in the picture.
- **Axes match** (step 8): the best-fit rotation between the two models' 3D points is never a
  reflection, and is 4° to 5° on flat open hands (up to 25° on fists, where the models disagree
  about the pose itself).
- **WiLoR's 3D points are not centred on the hand.** The wrist sits about 9.6 cm from the origin, so
  Phase 4's normalisation (wrist at the origin) has to come before any comparison.
- **WiLoR-mini does not need Python 3.10.** It gives identical output on 3.12. It does need two
  things its requirements leave out: `dill`, and `pip` in the build environment for chumpy.
- Both models miss hands the other finds. In the 83 labelled pictures MediaPipe was given, the
  teacher found 15 hands MediaPipe did not, and MediaPipe found 7 the teacher did not.

### First real recording (`hard-1`, 50 s, 1,510 pictures, every fifth labelled)

- Recording works on the real camera: 30.0 frames a second, no gaps, 24 ms from capture to
  landmarks, 164 kB a picture (about 300 MB a minute). Labelling took 0.77 s a picture.
- In the picture the two models mostly agree: the worst fingertip differs by a median of 0.11 palm
  lengths, and by more than 0.3 in 3% of frames. Handedness agreed in all 286 matched hands.
- **The teacher straightens bent fingers.** In 35 of 285 frames MediaPipe has a finger bent where
  the teacher has it straight; the reverse happens once. In the four such frames inspected by eye
  (1.8, 2.5, 20.3 and 30.0 s: a middle or ring finger folded to the thumb, the others extended)
  MediaPipe was right and the teacher drew a finger that is not there.
- **The teacher is better on sideways pinches.** With the hand side-on and all fingertips meeting
  the thumb (39.8 and 4.2 s), MediaPipe put thumb and index 0.37 to 0.50 palm lengths apart in 3D
  and the teacher 0.04 to 0.10; the pictures show them touching. At 39.8 s HoloTouch read the pinch
  0.3 s late.
- The teacher also errs the other way: at 24.5 s it reads 0.21 where the picture shows a clear gap
  between thumb and fingers.
- The problem is small in this sample. The teacher has the fingers together while MediaPipe has
  them past the release point (0.42) in 3 of 286 frames. HoloTouch's own tracker shows two short
  interruptions of an index pinch that resume, and in neither is it clear the fingers stayed closed.
- MediaPipe lost the hand in 67 of 1,510 frames; the teacher found a hand MediaPipe missed in 3 of
  302.

Scrolling (13.1 to 18.0 s of the same recording, every picture labelled, 147 frames):

- **What breaks.** When the two fingers tip steeply down (tilt past 90°, 20 frames), MediaPipe reads
  the middle finger as bent in half the frames. The pose leaves "two-finger", and HoloTouch pauses the
  scroll and then ends it (16.0 to 16.3 s when the recording is replayed through the engine).
- **The teacher reads the middle finger better** (straight in 85% of steep frames against 50%).
- **Fed to HoloTouch's pose rules, the teacher's hands would scroll worse.** It reads the ring or
  pinky as straight in every steep frame and in 81% of moderately tilted ones (MediaPipe: 5% and
  0%), which the rules call an open hand, and an open hand ends scrolling. It keeps the two-finger
  pose in 3 of 20 steep frames against MediaPipe's 12. The teacher may be right about those fingers:
  they are folded at the knuckle but otherwise straight. The two-finger rule tells extended from
  folded by straightness alone, and so depends on MediaPipe under-reading folded fingers.
- Top scroll speed is reached at 40° of lean, well before the readings turn unreliable near 100°,
  so the exact angle of a steep tilt does not matter; staying in the gesture does.

Scroll-only recording (`scroll-1`, 32 s, seven repeats of: pose, hold still, tip steeply down for
two seconds, come back up, open the hand), replayed through the engine:

- **Before:** during the steep holds the hand read as neutral three times, as an index pinch three
  times and as a fist once. Scrolling ran at full speed for 0% to 14% of each hold, the window under
  the hand was grabbed and dragged three times, and it was closed once.
- **The tilt reading survives when the pose does not.** Through every steep hold it stayed past
  100° (running on through 180°) whatever the pose was read as.
- **Fixed in the gesture, without a model** (`core/interactions/scroll.py`): while the tilt reads
  90° or more the scroll carries on whatever the pose; any other unclear pose pauses it for up to
  0.3 s; and a pinch or fist read as it ends starts nothing. After: full speed for 96% to 97% of
  each hold, seven scrolls for seven repeats, no window touched.
- **A second fault, also fixed:** the tilt reads about 33° as the pose is made from an open hand and
  climbs to about 60° over the next 0.3 s. Rest was taken after 0.15 s, so in five of the seven
  repeats the page scrolled 3 to 10 notches while the fingers were only being held up. Rest is now
  taken after 0.35 s, and that drops to 0.3 notches at most.
- The cost: a real fist or pinch made in the middle of a scroll also reads steep, so it scrolls
  down until the fingers come back up or the hand opens.

The go/no-go call on distillation has not been made. Review pictures are in
`recordings/hard-1.review/`.

### Where this went instead: labelled recordings and a benchmark

Distillation is parked. The teacher was not reliable enough on these poses, and the one problem
named as the main one was fixed in the gesture. What replaced it:

- A quick trial showed the signal is in MediaPipe's own landmarks. A classifier on the 21 points of
  single frames, trained on `scroll-1` and `hard-1` with rough labels, told a steep two-finger tilt
  from a real pinch or fist: 292 of 297 held-out steep frames right, 0 of 388 pinch frames and 2 of
  285 fist frames called steep, and all 18 steep frames of the other recording recognised.
- `holotouch collect` records while prompting one pose after another, so the recording says what the
  hand was doing, and whose hand it was.
- `holotouch score` measures the current rules against such recordings: what each prompted pose was
  read as, and which gesture it set off.

First labelled session (`me-right-1`, two rounds, 26 holds), scored by `holotouch score`:

- **Index pinches were missed entirely**: 0 of the 3 genuine pinch holds, though the pictures show
  the fingertips touching. MediaPipe's metric landmarks put them 0.34, 0.40 and 0.86 palm lengths
  apart (the limit is 0.25); its picture landmarks put them 0.03, 0.16 and 0.11 apart. The pinch is
  now the smaller of the two measures, with fingertips that merely line up in depth ruled out. All
  three are read, `scroll-1` is unchanged and `hard-1` has one grab that no longer drops out.
- The cost: a cupped hand waved about during "anything else" was read as a pinch once. A loosely
  closed hand near the head was read as a fist, and started a close, before and after.
- **A fist straight after scrolling kept scrolling**, since a fist also reads as a steep tilt. Its
  index finger reads 0.3 to 0.55 straight against 0.7 and more for fingers tipped down (441 and 573
  frames), so the steep hold now also needs the index finger above 0.6.
- Steep tilts in this new session scrolled in 2 of 2 holds for all of each hold.
- Right gesture, or rightly none: 23 of 26 holds, from 16 as first scored (5 of those were the
  scorer letting a switcher opened by one hold run on into the next).

First model (`holotouch train`, two sessions, one per hand, each read by a model trained on the
other): a tie with the rules, 48 of 52 holds and 83% of frames each. The model reads a steep tilt as
two fingers in 48% of frames (rules: 0%) and an open hand in 65% (25%), but keeps a pinch up for
only 74% of a hold (100%) and a fist for 76%. Described by raw coordinates it was much worse (41 of
52); described by the distances between joints, which do not change as the hand turns, it tied. A
model trained on one round of a recording read the other round only 72% to 92% right: a pose held
still is one example however many frames it fills, and there are four holds a pose. It is not
switched on.

Next: more labelled sessions (other hand, other light, other people), then a small model on the
landmarks and their recent history, measured with the same command. What is left for it on this
evidence is telling a cupped or loosely closed hand from a pinch or a fist.

## Constraints

**Hardware.** AMD Ryzen 7 PRO 8840HS (8 cores, 16 threads, AVX-512), 58 GB RAM, integrated Radeon
780M graphics, no discrete GPU. Anything that runs live must run on CPU within a 30 fps budget
alongside MediaPipe.

**Software.** HoloTouch pins Python 3.12 and `mediapipe==1.0.1`. The tracker runs in its own process
and sends only landmarks to the core.

**Testing.** Never test on the live display. Use `--dry-run`, `--replay`, or a private Xvfb with its
own xfwm4.

## Where occlusion hurts in the current code

| Location | What happens |
|---|---|
| `src/holotouch/tracker/landmarker.py:85` | The handedness score is captured and never used. Nothing else carries confidence, so a hidden fingertip is treated as a measured one. |
| `src/holotouch/core/poses.py:73` | Pinch distance is a 3D thumb-to-fingertip distance. Depth is the part a monocular model guesses when a fingertip is hidden. |
| `src/holotouch/core/poses.py:79` | Finger tilt for scrolling is purely depth against height. |
| `src/holotouch/config.py:80` | `pinch_off_ms` is 60 ms, two frames at 30 fps. Two bad frames release a grab. |
| `src/holotouch/core/hands.py:185` | After `lost_grace_ms` (250 ms) without a detection the hand is deleted. |
| `src/holotouch/core/hands.py:80` | A re-detected hand gets a new id and cannot arm while it is still pinching, so an interrupted drag never resumes. |

## Papers reviewed

Four arXiv papers were read in full. The ACM paper's PDF returned 403, so only its abstract was
available. Deformer was read in full afterwards, together with its repository and issue tracker.

| Paper | What it is | Verdict for HoloTouch |
|---|---|---|
| [WiLoR](https://arxiv.org/abs/2409.12259) (2409.12259) | Fast hand detector plus a transformer 3D reconstructor | Most useful. Much lower frame-to-frame jitter than HaMeR (5.92 vs 20.43 on HO3D) with no temporal module. The detector is 7–25 MB and far more robust than MediaPipe's (AP@0.5 of 96 vs 53 on their WHIM set), but its 138–175 FPS was measured on an RTX 4090. The reconstructor is a large ViT; a FastViT variant lost accuracy. Use it as the offline teacher. |
| [HaMeR](https://arxiv.org/abs/2312.05251) (2312.05251) | ViT-H single-frame reconstructor | Too heavy to run live. Even this model scores 27.2% on occluded joints against 60.8% on visible ones (PCK@0.05, New Days), so no model swap makes occlusion go away. Its HInt dataset has per-keypoint occlusion labels. Possible second teacher. |
| [HaWoR](https://arxiv.org/abs/2501.02973) (2501.02973) | Egocentric world-space hand motion with SLAM | Low. The SLAM half is irrelevant with a fixed webcam, and the authors call it "far from real-time" (40 ms per frame on GPU). The motion infiller needs start and end frames as context, so it is not causal. Only the idea transfers: fill a gap with a motion prior instead of dropping the hand. |
| [TempCLR](https://arxiv.org/abs/2209.00489) (2209.00489) | Contrastive pre-training recipe on unlabelled video | Lowest. It only matters when training a pixel-level model. Its acceleration-error metric is worth borrowing for replay tests. |
| Redirected Pinch (CHI 2026, DOI 10.1145/3772318.3791512) | VR interaction technique, abstract only | Design, not tracking. Maps hand movement on a waist-height plane to a vertical window with pinch as confirmation, and finds pinch tolerates that remapping better than touch. Supports the pinch-to-confirm design and suggests a lower, more comfortable hand zone. |
| [Deformer](https://arxiv.org/abs/2303.04991) (2303.04991) | Temporal transformer that fuses neighbouring frames by learned confidence | Not usable. See below. |

### Why Deformer is not an option

- **No weights exist.** The author states the checkpoints were lost in a lab NAS cleanup and will
  not be retrained ([issue #10](https://github.com/fuqichen1998/Deformer/issues/10)).
- **No inference path.** The [repository](https://github.com/fuqichen1998/Deformer) only trains and
  evaluates on HO3D and DexYCB. A request for a custom-video demo got the same answer
  ([issue #5](https://github.com/fuqichen1998/Deformer/issues/5)).
- **Training is a large job.** The paper used 8 RTX 2080Ti GPUs for 60 epochs. One user reports
  about 7 days on 8 A800s, and another could not reproduce the results after two attempts.
- **It is not causal.** It fuses 7 frames sampled 10 frames apart (2–3 seconds) and warps
  predictions both forward and backward in time.
- **Wrong kind of occlusion.** It is trained on hands holding objects in lab footage, not a bare
  hand hiding its own fingertips in front of a webcam.

What is worth keeping is the idea: each frame predicts a confidence, and low-confidence frames lean
on neighbouring frames instead of their own estimate.

### Other research

Titles and abstracts confirmed via arXiv:

- [MediaPipe Hands](https://arxiv.org/abs/2006.10214): the pipeline HoloTouch uses.
- [On-device Real-time Hand Gesture Recognition](https://arxiv.org/abs/2111.00038): builds on
  MediaPipe Hands and compares a heuristic gesture classifier with a small neural one on landmarks.
- [SmoothNet](https://arxiv.org/abs/2112.13715): temporal-only refiner aimed at the multi-frame
  errors occlusion causes. Believed to use a window with future frames.
- [HMP](https://arxiv.org/abs/2312.16737): hand motion priors for video; heavy, read for ideas.
- [HandOccNet](https://arxiv.org/abs/2203.14564): occlusion-robust mesh estimation; heavy.
- [InterWild](https://arxiv.org/abs/2303.13652): two interacting hands, relevant to resize.
- [RTMPose](https://arxiv.org/abs/2303.07399), [MobRecon](https://arxiv.org/abs/2112.02753),
  [SimpleHand](https://arxiv.org/abs/2403.01813): efficient models, see the next section.
- [HandPad](https://arxiv.org/abs/2607.11807): same group as Redirected Pinch; the non-dominant
  hand sets mode and target, the dominant hand manipulates.

From memory, not verified:

- Wolf et al., CHI 2020, the "Heisenberg effect": the act of confirming shifts the pointing
  position. Suggests picking the window from the hand position just before pinch onset.
- MEgATrack and UmeTrack (Meta): production multi-camera hand tracking. A second webcam at another
  angle is the most direct fix for self-occlusion and would give real depth.

## Models that can run on a laptop

Each repository's existence and licence were checked. None were benchmarked on this CPU.

| Model | Live on this CPU? | Notes |
|---|---|---|
| MediaPipe Hands | Yes | Current tracker. 3D landmarks, no per-joint confidence. |
| RTMPose via [rtmlib](https://github.com/Tau-J/rtmlib) | Likely | Apache-2.0, plain ONNX. 2D keypoints with per-keypoint confidence. That it ships a hand model is from memory. |
| [MobRecon](https://github.com/SeanChenxy/HandMesh), [SimpleHand](https://github.com/patienceFromZhou/simpleHand) | Possibly | MIT. Designed for speed, output a full mesh. Weight availability not checked. |
| [WiLoR-mini](https://github.com/warmshao/WiLoR-mini) | No, offline only | Pip-installable, downloads weights, falls back to CPU. Needs Python 3.10. No licence declared. |
| [WiLoR](https://github.com/rolpotamias/WiLoR) | No, offline only | Official repo with a Colab notebook and Hugging Face demo. Models are CC-BY-NC-ND. |
| [HaMeR](https://github.com/geopavlakos/hamer) | No, offline only | MIT code, very large model, needs MANO registration. |

## Candidate directions

Novelty has not been confirmed by a literature search; treat these as candidates.

1. **Contact sensing judged by interaction outcomes.** Vision papers optimise millimetre joint
   error. A window manager needs the moment of pinch contact and release. Train a contact model
   against physically measured truth and report dropped grabs, false activations and pointing
   throughput.
2. **A causal, uncertainty-aware refiner.** Every occlusion method reviewed uses future frames or a
   large GPU. A small model that sees only past frames, outputs corrected landmarks plus per-joint
   confidence, and is distilled from an offline teacher would fill that gap.
3. **Interface state as a prior.** HoloTouch knows the user is mid-drag. Staying pinched is likely, and
   release should need positive evidence rather than two bad frames. No training needed to start.
4. **Calibrated hand size for depth.** Measure the user's bone lengths once and estimate distance
   from apparent size. Least novel, but could enable push/pull gestures.

The chosen path is direction 2, ideally combined with direction 1, because both are feasible on
this laptop and HoloTouch's replay mode already provides a testbed.

## The distillation idea

WiLoR is much better than MediaPipe on hard frames but cannot run at 30 fps here. MediaPipe can, but
gives confident nonsense when a fingertip is hidden. Distillation moves some of WiLoR's judgement
into something that fits the frame budget.

1. Record HoloTouch use, saving video and MediaPipe's landmarks for each frame.
2. Run WiLoR over the video afterwards with no time pressure. Every frame now has two answers.
3. Train a small student on those pairs. Input: the last few frames of MediaPipe landmarks. Target:
   what WiLoR said the hand was doing.
4. Run the student live after MediaPipe. It works on 21 points, not pixels, so it costs almost
   nothing.

The student is not a shrunken WiLoR and never sees the image. It learns the pattern of MediaPipe's
mistakes, for example that a thumb tip jumping 3 cm as the palm turns edge-on did not really move.
It can then flag the frame as unreliable, so the engine holds the pinch, and fill in a plausible
pose from the preceding frames.

**Limits.** It cannot recover information MediaPipe never had. If fingertips are hidden for a full
second and the user really releases, a landmark-only student cannot see that. It also inherits the
teacher's errors, which is why physical contact ground truth is a useful complement.

## Choosing and running the teacher

**WiLoR-mini is a repackaging, not a smaller model.** It downloads files named `wilor_final.ckpt`
and `detector.pt`, the same names the original repository uses. Outputs were not compared between
the two.

**A GPU changes speed, not label quality.** Where a GPU helps quality is indirectly:

- running two teachers (WiLoR and HaMeR) and keeping only frames where they agree;
- labelling an hour of footage instead of ten minutes;
- re-labelling quickly when the recording setup changes.

| Where | For | Against |
|---|---|---|
| Laptop CPU, overnight | Footage stays local, nothing to rent | Slow; untimed, so label 100 frames first and extrapolate |
| Colab or Kaggle free GPU | Fast, official WiLoR notebook exists | Footage is uploaded, session limits apply |
| Rented GPU by the hour | Fast at scale | Only worth it with hours of footage |

Recommended: do the first run on Colab with the official WiLoR notebook on a couple of minutes of
footage to reach the go/no-go check quickly. If the labels are good, switch to WiLoR-mini locally
for bulk labelling, or stay on Colab if the laptop is too slow.

## The plan

### Phase 1: Record video alongside landmarks

1. Add frame saving in the tracker process. Camera frames never leave `tracker/process.py`, so
   saving has to happen there, next to the `landmarker.submit` call.
2. Save each frame as a JPEG named by its capture time. MediaPipe's live mode silently drops frames
   under load, so frame counts will not line up. `FrameSample.t_capture` is the same number the
   camera returned, so it is an exact join key.
3. Save the mirrored frame, the one MediaPipe actually saw.
4. Save every camera frame, including ones the idle-skip logic does not submit.
5. Keep writing the existing JSONL from `holotouch record`.

Budget about 2 GB per ten minutes at 720p.

### Phase 2: Collect the right footage

Record separate sessions, because whole sessions are held out later.

- **Easy:** open palm, slow pinches facing the camera, at a few distances.
- **Hard on purpose:**
  - pinch with the palm edge-on, and pinch while rotating the wrist;
  - long drags across the whole mapping box;
  - two-hand resize with hands crossing and overlapping;
  - fist and two-finger tilt;
  - hands entering and leaving the frame edges;
  - fast motion.
- **Natural:** ten minutes of really using HoloTouch with `--dry-run`.
- **Negatives:** typing, reaching for a cup, touching the face.
- **Variation:** different lighting, sleeves, another day.

Start with 20–30 minutes in total.

### Phase 3: Label with the teacher

1. Use a separate environment. WiLoR-mini pins `torch<=2.5` and `ultralytics==8.1.34`, which
   HoloTouch's must not inherit. (It asks for Python 3.10 but runs the same on 3.12; see Status.)
2. Use float32 on CPU. The README example uses float16, which is meant for GPU.
3. Time 100 frames, then decide between laptop and Colab.
4. Run the teacher's own detector on every frame, not MediaPipe's boxes, to capture frames where
   MediaPipe lost the hand.
5. Keep per hand: the 21 3D keypoints, the 21 2D keypoints, the box, the handedness flag and the
   detector confidence.
6. Handedness needs no conversion: both models name a hand by how it looks in the picture. (This
   step first expected an inversion; see Status.)
7. Joint order already matches. WiLoR-mini reorders joints to wrist, thumb, index, middle, ring,
   pinky, the same as MediaPipe's 0–20.
8. Check the axes. On open-palm frames, align teacher and MediaPipe 3D points and confirm the
   rotation is near identity.

**Go/no-go.** Overlay the teacher's 2D keypoints on a few hundred hard frames and inspect them. If
the teacher is visibly wrong on pinch occlusions, stop and get ground truth from a second camera
instead.

### Phase 4: Clean and align the labels

1. Match teacher hands to MediaPipe hands per frame by palm-centre distance in the image.
2. Reject bad teacher frames: low detector confidence, box touching the image border, or a sudden
   jump in the teacher's own track.
3. Smooth the teacher track forwards and backwards in time. Using future frames is fine offline.
4. Mask gaps longer than about five frames from training rather than interpolating across them.
5. Normalise both sides the same way: wrist at the origin, divided by palm length, left hands
   mirrored to right so one model serves both.
6. Sort frames into three types: MediaPipe agrees with the teacher, MediaPipe disagrees, and
   MediaPipe has no hand but the teacher does.

Before training, count how often each type occurs. If almost all failures are total dropouts, a
landmark refiner is the wrong tool and the re-attach logic (a re-detected hand inheriting a recent
grab) is the fix instead.

### Phase 5: Train the student

- **Input per frame:** normalised MediaPipe world landmarks, normalised image landmarks, the
  handedness score, the time since the previous frame, and a "missing" flag.
- **Context:** the last 8–16 frames, past only.
- **Model:** a small recurrent network, well under a million parameters, stepping once per frame.
- **Output:** a correction added to MediaPipe's current landmarks, plus an uncertainty per joint.
- **Loss:**
  - a likelihood loss that lets the model widen its uncertainty where it is wrong, so confidence
    needs no separate labels;
  - extra weight on fingertips and on thumb-to-index distance.
- **Split by session, never by frame.** Neighbouring frames are near duplicates and would leak.
- **Augment:** small in-plane rotations, random dropped frames, light noise.

Training fits on the laptop CPU.

### Phase 6: Evaluate

Compare against raw MediaPipe and against the current 1€ filter path.

- **Landmark level:** thumb-to-index distance error against the teacher, on hard frames only.
- **State level:** run the pose classifier on teacher landmarks to get "true" pinch state, then
  count wrong frames.
- **Interaction level:** replay held-out sessions through the engine with `--replay --dry-run` and
  count dropped grabs and false pinches.

### Phase 7: Integrate

1. Export the student to a format that runs on CPU without torch.
2. Insert it in `Hand._ingest` (`src/holotouch/core/hands.py:59`), before `extract_features`, with
   state kept per hand and reset for new hands.
3. Feed uncertainty into `PoseTracker`: while thumb or index uncertainty is high, hold the current
   pose instead of starting the release timer.
4. Re-tune the pinch thresholds. The teacher places joints slightly differently from MediaPipe, so
   ratios such as `pinch_enter` will shift.
5. Fall back to the current path when the model file is absent.

## Optional: physical contact ground truth

Conductive foil on the thumb and index finger, wired to a microcontroller, gives exact pinch on and
off timing. This is truth the teacher cannot provide, since it is also unreliable when fingertips
are hidden. It supports direction 1 and gives an independent check on the student.

## Risks and caveats

- **The teacher is also wrong under occlusion.** HaMeR's occluded-joint score is less than half its
  visible-joint score. The Phase 3 go/no-go check exists for this reason.
- **Privacy.** Uploading webcam footage to a hosted notebook includes the face unless frames are
  cropped to the hands first.
- **Licences.** WiLoR's models are CC-BY-NC-ND and depend on Ultralytics and the MANO model, each
  with its own terms. HaMeR's code is MIT but also needs MANO. This is fine for personal research.
  How these terms apply to a student trained on teacher outputs was not established; check before
  releasing one.
- **Cheaper alternatives exist.** A hand-written reliability signal (palm edge-on, handedness-score
  dips, bone-length jumps) that holds the pose, plus the re-attach logic, needs no model and may
  capture much of the gain. It is worth trying first or alongside.

## What was and was not verified

Verified in the session:

- Full text of WiLoR, HaMeR, HaWoR, TempCLR and Deformer.
- Deformer's repository, README and issue threads.
- WiLoR-mini's pipeline source, joint-order mapping and requirements.
- Existence and licence of each repository listed.
- This machine's CPU, memory and graphics.

Not verified:

- Redirected Pinch beyond its abstract.
- Speed of any model on this CPU, other than WiLoR-mini (see Status).
- That WiLoR-mini's outputs match the original WiLoR's.
- That rtmlib ships a hand model, and that SmoothNet's window is non-causal.
- Free GPU quotas on Colab and Kaggle.
- The papers cited from memory (Heisenberg effect, MEgATrack, UmeTrack).
- Novelty of the candidate directions.

# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = [
#     "wilor-mini @ git+https://github.com/warmshao/WiLoR-mini@ebec42f94c389070cdd7dda6fd1bf0b4a659c960",
#     "torch==2.5.0",
#     "torchvision==0.20.0",
#     "dill",  # the detector's weights were saved with it
# ]
#
# [tool.uv.extra-build-dependencies]
# chumpy = ["pip"]  # its setup.py imports pip without saying so
#
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# torchvision = { index = "pytorch-cpu" }
#
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Label a recording's camera pictures with WiLoR, a slow but accurate hand model (the "teacher").

    uv run research/label_teacher.py recordings/session.jsonl

Takes a recording made with `holowm record --frames`, reads the pictures in
recordings/session.frames and writes recordings/session.teacher.jsonl: one line per picture,
holding every hand the teacher found. Pictures already labelled are skipped, so a run that was
stopped carries on where it left off.

This runs in an environment of its own, which uv builds from the header above; it shares nothing
with HoloWM's. The first run downloads the model (2.6 GB) to ~/.cache/holowm/wilor.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

WEIGHTS_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "holowm" / "wilor"
BONES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (5, 9), (9, 10), (10, 11), (11, 12),
         (9, 13), (13, 14), (14, 15), (15, 16), (13, 17), (17, 18), (18, 19), (19, 20), (0, 17)]  # fmt: skip


class Teacher:
    def __init__(self, confidence: float):
        import torch
        from wilor_mini.pipelines.wilor_hand_pose3d_estimation_pipeline import WiLorHandPose3dEstimationPipeline

        gpu = torch.cuda.is_available()
        self.confidence = confidence
        self.detect_s = self.pose_s = 0.0
        self.pipeline = WiLorHandPose3dEstimationPipeline(
            device=torch.device("cuda" if gpu else "cpu"),
            dtype=torch.float16 if gpu else torch.float32,  # half precision is only for a GPU
            wilor_pretrained_dir=str(WEIGHTS_DIR),
            verbose=False,
        )

    def label(self, rgb: np.ndarray) -> list[dict]:
        """Every hand in the picture, found by the teacher's own detector."""
        height, width = rgb.shape[:2]
        start = time.perf_counter()
        # One row per hand: the box's corners, the detector's confidence, and 1 for a right hand.
        boxes = self.pipeline.hand_detector(rgb, conf=self.confidence, verbose=False)[0].boxes.data.cpu().numpy()
        self.detect_s += time.perf_counter() - start
        if not len(boxes):
            return []
        start = time.perf_counter()
        results = self.pipeline.predict_with_bboxes(rgb, boxes[:, :4], boxes[:, 5])
        self.pose_s += time.perf_counter() - start
        hands = []
        for box, result in zip(boxes, results):
            prediction = result["wilor_preds"]
            hands.append(
                {
                    # Named by how the hand looks in the picture, which is how the recording names
                    # it too. The picture is mirrored, so it is the user's other hand.
                    "handedness": "Right" if box[5] else "Left",
                    "confidence": round(float(box[4]), 4),
                    # Positions in the picture are fractions of its size, as in the recording.
                    "box": np.round(box[:4] / (width, height, width, height), 5).tolist(),
                    "image": np.round(prediction["pred_keypoints_2d"][0] / (width, height), 5).tolist(),
                    "world": np.round(prediction["pred_keypoints_3d"][0].astype(float), 5).tolist(),  # metres
                }
            )
        return hands


def read_lines(path: Path) -> list[dict]:
    """The file's whole lines; a last line cut short by a stopped run is removed from the file."""
    if not path.exists():
        return []
    text = path.read_text()
    whole = text[: text.rfind("\n") + 1]
    if whole != text:
        path.write_text(whole)
    return [json.loads(line) for line in whole.splitlines()]


def duration(seconds: float) -> str:
    return f"{seconds / 3600:.1f} h" if seconds >= 5400 else f"{seconds / 60:.0f} min"


def label_pictures(todo: list[Path], out_path: Path, confidence: float, remaining: int) -> None:
    print(f"loading the teacher (the first run downloads 2.6 GB to {WEIGHTS_DIR}) ...", flush=True)
    teacher = Teacher(confidence)
    hands = 0
    begun = reported = time.perf_counter()
    with out_path.open("a") as out:
        for done, path in enumerate(todo, start=1):
            found = teacher.label(cv2.cvtColor(cv2.imread(str(path)), cv2.COLOR_BGR2RGB))
            hands += len(found)
            out.write(json.dumps({"t_us": int(path.stem), "hands": found}) + "\n")
            out.flush()
            now = time.perf_counter()
            if now - reported > 15.0 or done == len(todo):
                reported = now
                each = (now - begun) / done
                print(f"{done}/{len(todo)} pictures, {each:.2f} s each, {duration(each * (len(todo) - done))} left", flush=True)
    each = (time.perf_counter() - begun) / len(todo)
    print(
        f"labelled {len(todo)} pictures with {hands} hands: {each:.2f} s a picture "
        f"({teacher.detect_s / len(todo) * 1000:.0f} ms finding hands, "
        f"{teacher.pose_s / max(hands, 1):.2f} s for each hand found)"
    )
    if remaining:
        print(f"the {remaining} pictures still unlabelled would take about {duration(each * remaining)} at this rate")


def draw_hand(picture: np.ndarray, points: np.ndarray, colour: tuple[int, int, int]) -> None:
    height, width = picture.shape[:2]
    pixels = [(round(x * width), round(y * height)) for x, y in points[:, :2]]
    for a, b in BONES:
        cv2.line(picture, pixels[a], pixels[b], colour, 1, cv2.LINE_AA)
    for pixel in pixels:
        cv2.circle(picture, pixel, 3, colour, -1, cv2.LINE_AA)


def draw_overlays(recording: Path, frames_dir: Path, labels: list[dict], overlay_dir: Path) -> None:
    """Each labelled picture with the teacher's hands in green over the recording's in red."""
    recorded = {round(frame["t_capture"] * 1e6): frame["hands"] for frame in read_lines(recording)}
    overlay_dir.mkdir(exist_ok=True)
    for label in labels:
        name = f"{label['t_us']:015d}.jpg"
        picture = cv2.imread(str(frames_dir / name))
        height, width = picture.shape[:2]
        for hand in recorded.get(label["t_us"], []):
            draw_hand(picture, np.array(hand["image"]), (0, 0, 255))
        for hand in label["hands"]:
            draw_hand(picture, np.array(hand["image"]), (0, 255, 0))
            x, y = round(hand["box"][0] * width), round(hand["box"][1] * height)
            cv2.rectangle(picture, (x, y), (round(hand["box"][2] * width), round(hand["box"][3] * height)), (0, 255, 0), 1)
            caption = f"{hand['handedness']} {hand['confidence']:.2f}"
            cv2.putText(picture, caption, (x, max(y - 6, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
        tracked = "" if label["t_us"] in recorded else "  (not given to MediaPipe)"
        cv2.putText(picture, "teacher", (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.putText(picture, "MediaPipe" + tracked, (10, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)
        cv2.imwrite(str(overlay_dir / name), picture)
    print(f"drew {len(labels)} pictures in {overlay_dir}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("recording", type=Path, help="the .jsonl file written by `holowm record --frames`")
    parser.add_argument("--every", type=int, default=1, metavar="N", help="label only every Nth picture")
    parser.add_argument("--limit", type=int, metavar="N", help="stop after labelling N pictures, to time the teacher")
    parser.add_argument("--confidence", type=float, default=0.3, help="lowest detector confidence that counts as a hand")
    parser.add_argument(
        "--overlay",
        action="store_true",
        help="also draw every labelled picture, with both models' hands on it, in a directory ending .overlay",
    )
    args = parser.parse_args(argv)

    frames_dir = args.recording.with_suffix(".frames")
    pictures = sorted(frames_dir.glob("*.jpg"))
    if not pictures:
        print(f"no pictures in {frames_dir}; record with `holowm record --frames`", file=sys.stderr)
        return 2
    out_path = args.recording.with_suffix(".teacher.jsonl")
    done = {label["t_us"] for label in read_lines(out_path)}
    unlabelled = [p for p in pictures[:: args.every] if int(p.stem) not in done]
    todo = unlabelled[: args.limit]
    if todo:
        label_pictures(todo, out_path, args.confidence, len(pictures) - len(done) - len(todo))
    else:
        print(f"all {len(pictures[:: args.every])} pictures are already labelled in {out_path}")
    if args.overlay:
        labels = sorted(read_lines(out_path), key=lambda label: label["t_us"])
        draw_overlays(args.recording, frames_dir, labels, args.recording.with_suffix(".overlay"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

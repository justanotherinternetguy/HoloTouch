"""Command line entry point. Heavy imports stay inside the subcommands that need them."""

from __future__ import annotations

import argparse
import getpass
import logging
import socket
import sys
import time
from pathlib import Path

from holowm.config import CONFIG_DIR, SOCKET_PATH, Config, load_config


def _cmd_run(args) -> int:
    cfg = load_config(args.config)
    if args.debug:
        cfg.ui.debug = True
    if args.replay and args.record:
        raise ValueError("--record needs the camera; it cannot be used with --replay")
    if args.frames and not args.record:
        raise ValueError("--frames goes with --record FILE")
    frames_dir = _frames_dir(args.record, args.frames) if args.record else None
    from holowm.overlay.app import App
    from holowm.tracker.source import RecordingSource, ReplaySource, TrackerSource

    if args.dry_run:
        from PySide6.QtWidgets import QApplication

        from holowm.core.actions import WindowInfo
        from holowm.x11.fake import FakeBackend

        qt = QApplication(["holowm"])
        size = qt.primaryScreen().size()
        backend = FakeBackend((size.width(), size.height()), verbose=True)
        # Stand-in windows, so gestures have something to act on without touching real ones.
        w, h = size.width(), size.height()
        backend.add_window(WindowInfo(1, w // 10, h // 8, w * 4 // 10, h // 2, title="Demo one"))
        backend.add_window(WindowInfo(2, w // 2, h // 3, w * 4 // 10, h // 2, title="Demo two"))
    else:
        from holowm.x11.backend import X11Backend

        backend = X11Backend(cfg.gesture.scroll_backend)
    if args.replay:
        source = ReplaySource(args.replay, loop=args.loop)
    else:
        source = TrackerSource(cfg, frames_dir)
        if args.record:
            source = RecordingSource(source, args.record)
    code = App(cfg, backend, source, exit_when_done=bool(args.replay) and not args.loop).run()
    if args.record:
        _report_recording(source, frames_dir)
    return code


def _frames_dir(file: Path, frames: bool) -> Path | None:
    """Where a recording's camera pictures go, if they are wanted."""
    frames_dir = file.with_suffix(".frames") if frames else None
    if frames_dir is not None and frames_dir.exists() and any(frames_dir.iterdir()):
        raise ValueError(f"{frames_dir} already holds frames; record under another name or remove it")
    return frames_dir


def _report_recording(source, frames_dir: Path | None) -> None:
    print(f"wrote {source.count} frames")
    if frames_dir is not None:
        pictures = list(frames_dir.glob("*.jpg"))
        size = sum(p.stat().st_size for p in pictures) / 1e6
        print(f"saved {len(pictures)} camera pictures ({size:.0f} MB) in {frames_dir}")


def _cmd_record(args) -> int:
    from holowm.tracker.source import RecordingSource, TrackerSource

    frames_dir = _frames_dir(args.file, args.frames)
    source = RecordingSource(TrackerSource(load_config(args.config), frames_dir), args.file)
    print(f"recording {args.seconds:.0f} s of hand tracking to {args.file} ...")
    deadline = time.monotonic() + args.seconds
    try:
        while time.monotonic() < deadline:
            if source.error:
                print(f"tracker error: {source.error}", file=sys.stderr)
                return 1
            source.drain()
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    finally:
        source.stop()
    _report_recording(source, frames_dir)
    return 0


def _cmd_collect(args) -> int:
    cfg = load_config(args.config)
    cfg.ui.debug = True  # the panel shows whether the hand is in view and tracked
    labels = args.file.with_suffix(".labels.json")
    if labels.exists():
        raise ValueError(f"{labels} already exists; record under another name or remove it")
    frames_dir = _frames_dir(args.file, args.frames)
    from holowm.tools.prompts import Prompter

    prompter = Prompter(rounds=args.rounds, only=set(args.only.split(",")) if args.only else None)  # checked before anything starts
    from PySide6.QtWidgets import QApplication

    from holowm.overlay.app import App
    from holowm.tracker.source import RecordingSource, TrackerSource
    from holowm.x11.fake import FakeBackend

    qt = QApplication(["holowm"])
    size = qt.primaryScreen().size()
    backend = FakeBackend((size.width(), size.height()))  # no windows: nothing here acts on anything
    source = RecordingSource(TrackerSource(cfg, frames_dir), args.file)
    code = App(cfg, backend, source, prompter=prompter).run()
    prompter.save(labels, args.person)
    _report_recording(source, frames_dir)
    print(f"labelled {len(prompter.done)} of {len(prompter.plan)} poses in {labels}")
    return code


def _cmd_score(args) -> int:
    from holowm.tools.score import run_score

    cfg = load_config(args.config)
    if args.model is not None:
        cfg.pose.model = str(args.model)
    return run_score(args.files, cfg)


def _cmd_train(args) -> int:
    from holowm.tools.train import run_train

    return run_train(args.files, load_config(args.config), args.out)


def _cmd_doctor(args) -> int:
    from holowm.tools.doctor import run_doctor

    return run_doctor(load_config(args.config), measure=not args.no_camera)


def _cmd_panel(args) -> int:
    if args.install:
        from holowm.panel.desktop import install_launcher

        print(f"added HoloWM to the applications menu: {install_launcher()}")
        return 0
    from holowm.panel.app import run_panel

    # Opened from the applications menu there is no terminal to complain to, so a config file
    # that cannot be read is reported in the panel itself.
    try:
        cfg, problem = load_config(args.config), ""
    except ValueError as exc:
        cfg, problem = Config(), f"The config file has a problem: {exc}"
    return run_panel(cfg, args.config, problem)


def _cmd_ctl(args) -> int:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        client.connect(str(SOCKET_PATH))
    except OSError:
        print("holowm is not running", file=sys.stderr)
        return 1
    with client:
        client.sendall(args.command.encode() + b"\n")
        client.settimeout(2.0)
        print(client.recv(256).decode().strip())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="holowm", description="Hand-gesture window control for XFCE/X11")
    parser.add_argument("--config", type=Path, default=None, help="config file (default ~/.config/holowm/config.toml)")
    parser.add_argument("-v", "--verbose", action="store_true")
    commands = parser.add_subparsers(dest="cmd")

    run = commands.add_parser("run", help="start tracking and the overlay (default)")
    run.add_argument("--debug", action="store_true", help="show the tracking diagnostics panel")
    run.add_argument("--dry-run", action="store_true", help="act on stand-in windows instead of real ones")
    run.add_argument("--replay", type=Path, help="drive the engine from a recording instead of the camera")
    run.add_argument("--loop", action="store_true", help="with --replay, repeat the recording")
    run.add_argument("--record", type=Path, metavar="FILE", help="also record the hand tracking to a JSONL file")
    run.add_argument("--frames", action="store_true", help="with --record, save every camera frame too, as `record --frames` does")
    run.set_defaults(func=_cmd_run)

    panel = commands.add_parser("panel", help="open the control panel: a window to start, stop and watch HoloWM from")
    panel.add_argument("--install", action="store_true", help="add the panel to the applications menu instead of opening it")
    panel.set_defaults(func=_cmd_panel)

    record = commands.add_parser("record", help="record hand tracking to a JSONL file for replay and tuning")
    record.add_argument("file", type=Path)
    record.add_argument("--seconds", type=float, default=15.0)
    record.add_argument(
        "--frames",
        action="store_true",
        help="also save every camera frame as a JPEG, in FILE's directory under the same name ending .frames",
    )
    record.set_defaults(func=_cmd_record)

    collect = commands.add_parser("collect", help="record while prompting one pose after another, so the recording is labelled")
    collect.add_argument("file", type=Path, help="the JSONL recording to write; its labels go beside it")
    collect.add_argument("--person", default=getpass.getuser(), help="whose hand this is (default: your login name)")
    collect.add_argument("--rounds", type=int, default=2, help="how many times to go through the poses (about a minute each)")
    collect.add_argument("--only", metavar="POSES", help="ask only for these poses, e.g. claw or pinch,fist (default: all of them)")
    collect.add_argument("--frames", action="store_true", help="save every camera frame too, as `record --frames` does")
    collect.set_defaults(func=_cmd_collect)

    score = commands.add_parser("score", help="measure how HoloWM reads the poses in recordings made by `collect`")
    score.add_argument("files", type=Path, nargs="+", help="recordings made by `holowm collect`")
    score.add_argument("--model", type=Path, help="read poses with this model instead of what is configured")
    score.set_defaults(func=_cmd_score)

    train = commands.add_parser("train", help="train a pose model on recordings made by `collect`")
    train.add_argument("files", type=Path, nargs="+", help="recordings made by `holowm collect`")
    train.add_argument("--out", type=Path, default=CONFIG_DIR / "pose_model.npz", help="where to save the model")
    train.set_defaults(func=_cmd_train)

    doctor = commands.add_parser("doctor", help="check that this machine has what HoloWM needs")
    doctor.add_argument("--no-camera", action="store_true", help="skip the live tracking measurement")
    doctor.set_defaults(func=_cmd_doctor)

    ctl = commands.add_parser("ctl", help="control a running instance")
    ctl.add_argument("command", choices=["pause", "resume", "toggle", "debug", "status", "quit"])
    ctl.set_defaults(func=_cmd_ctl)

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    if args.cmd is None:
        args = parser.parse_args([*(argv if argv is not None else sys.argv[1:]), "run"])
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"holowm: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

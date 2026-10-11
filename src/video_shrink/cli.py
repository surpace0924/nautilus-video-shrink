"""Command-line entry point: video-shrink --preset KEY FILE..."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from . import __version__
from .encoder import ShrinkError, shrink
from .presets import PresetError, load_presets


class Cancelled(Exception):
    pass


class ZenityProgress:
    """Progress dialog driven through zenity's stdin protocol."""

    def __init__(self, title: str):
        self.proc = subprocess.Popen(
            ["zenity", "--progress", "--title", title, "--percentage=0",
             "--auto-close", "--width=400"],
            stdin=subprocess.PIPE, text=True,
        )

    def update(self, fraction: float, message: str) -> None:
        if self.proc.poll() is not None:  # dialog closed / cancel pressed
            raise Cancelled
        try:
            self.proc.stdin.write(f"# {message}\n{int(fraction * 100)}\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            raise Cancelled from None

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                self.proc.stdin.write("100\n")
                self.proc.stdin.close()
            except BrokenPipeError:
                pass
            self.proc.wait()


def notify(summary: str, body: str = "") -> None:
    subprocess.run(["notify-send", "-a", "Video Shrink", summary, body], check=False)


def gui_error(message: str) -> None:
    subprocess.run(["zenity", "--error", "--title", "Video Shrink",
                    "--text", message], check=False)


def console_progress(fraction: float, message: str) -> None:
    print(f"\r{message} {fraction * 100:5.1f}%", end="", file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="video-shrink", description="Shrink videos to a target file size.")
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("-p", "--preset", default="discord")
    parser.add_argument("--gui", action="store_true",
                        help="report progress and results with zenity / notify-send")
    parser.add_argument("--list-presets", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    try:
        presets = load_presets()
    except PresetError as e:
        gui_error(str(e)) if args.gui else print(f"error: {e}", file=sys.stderr)
        return 2
    if args.list_presets:
        for p in presets.values():
            print(f"{p.key}\t{p.size_mb:g}MB\t{p.codec}\t{p.label}")
        return 0
    if not args.files:
        parser.error("no input files")
    if args.preset not in presets:
        parser.error(f"unknown preset {args.preset!r} (see --list-presets)")
    preset = presets[args.preset]

    failures = 0
    for i, src in enumerate(args.files, 1):
        header = f"[{i}/{len(args.files)}] {src.name}"
        dialog = ZenityProgress(f"{preset.label}: {src.name}") if args.gui else None
        progress = dialog.update if dialog else console_progress
        try:
            dst = shrink(src, preset, lambda f, m: progress(f, f"{header} {m}"))
        except Cancelled:
            notify("Cancelled", src.name)
            return 130
        except (ShrinkError, OSError) as e:
            failures += 1
            msg = f"{src.name}: {e}"
            gui_error(msg) if args.gui else print(f"\nerror: {msg}", file=sys.stderr)
            continue
        finally:
            if dialog:
                dialog.close()

        if dst is None:
            msg = f"{src.name} is already {preset.size_mb:g}MB or smaller"
        else:
            msg = f"{dst.name} ({dst.stat().st_size / 1_000_000:.1f}MB)"
        notify("Done", msg) if args.gui else print(f"\n{msg}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

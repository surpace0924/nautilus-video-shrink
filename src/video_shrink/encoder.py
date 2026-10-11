"""Two-pass ffmpeg encoding to hit a target file size."""

from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .presets import Preset

# Fraction of the target size budgeted for audio+video; the rest absorbs
# container overhead and rate-control error.
SIZE_MARGIN = 0.95
MIN_VIDEO_KBPS = 50
MAX_RETRIES = 2

# (minimum video kbps, short-side resolution). Lower bitrates get a smaller
# frame so the result stays watchable instead of a blocky mess.
RESOLUTION_LADDER = [
    (2500, 1080),
    (1200, 720),
    (500, 480),
    (0, 360),
]

CODEC_SETTINGS = {
    "h264": {
        "ext": "mp4",
        "video": ["-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p"],
        "audio": ["-c:a", "aac"],
        "pass1": [],
        "pass2": ["-movflags", "+faststart"],
    },
    "vp9": {
        "ext": "webm",
        "video": ["-c:v", "libvpx-vp9", "-row-mt", "1", "-deadline", "good"],
        "audio": ["-c:a", "libopus"],
        "pass1": ["-cpu-used", "4"],
        "pass2": ["-cpu-used", "2"],
    },
}

# progress(fraction 0.0-1.0, message)
ProgressCallback = Callable[[float, str], None]


class ShrinkError(Exception):
    pass


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    width: int
    height: int
    has_audio: bool


@dataclass(frozen=True)
class EncodePlan:
    video_kbps: int
    audio_kbps: int
    short_side: int | None  # None = keep source resolution


def probe(path: Path) -> MediaInfo:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ShrinkError(f"ffprobe failed: {result.stderr.strip()}")
    data = json.loads(result.stdout)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        raise ShrinkError("no video stream found")
    duration = float(data["format"].get("duration") or video.get("duration") or 0)
    if duration <= 0:
        raise ShrinkError("could not determine duration")
    return MediaInfo(
        duration=duration,
        width=int(video["width"]),
        height=int(video["height"]),
        has_audio=any(s["codec_type"] == "audio" for s in data["streams"]),
    )


def plan_encode(info: MediaInfo, target_bytes: int, audio_kbps: int) -> EncodePlan:
    if not info.has_audio:
        audio_kbps = 0
    total_kbps = target_bytes * 8 / 1000 * SIZE_MARGIN / info.duration
    video_kbps = total_kbps - audio_kbps
    # Tight budget: give some of the audio share back to video.
    if audio_kbps and video_kbps < 300:
        audio_kbps = min(audio_kbps, 48)
        video_kbps = total_kbps - audio_kbps
    if video_kbps < MIN_VIDEO_KBPS:
        raise ShrinkError(
            f"video too long for the target size "
            f"({info.duration:.0f}s needs at least "
            f"{(MIN_VIDEO_KBPS + audio_kbps) * info.duration / 8 / 1000 / SIZE_MARGIN:.1f}MB)"
        )
    ladder_side = next(side for kbps, side in RESOLUTION_LADDER if video_kbps >= kbps)
    source_side = min(info.width, info.height)
    return EncodePlan(
        video_kbps=int(video_kbps),
        audio_kbps=audio_kbps,
        short_side=ladder_side if ladder_side < source_side else None,
    )


def output_path(src: Path, preset: Preset) -> Path:
    ext = CODEC_SETTINGS[preset.codec]["ext"]
    candidate = src.with_name(f"{src.stem}_{preset.key}.{ext}")
    n = 1
    while candidate.exists():
        candidate = src.with_name(f"{src.stem}_{preset.key}-{n}.{ext}")
        n += 1
    return candidate


def _scale_filter(short_side: int) -> list[str]:
    # Constrain the shorter side so portrait videos are handled too.
    s = short_side
    return ["-vf", f"scale=w='if(gt(iw,ih),-2,{s})':h='if(gt(iw,ih),{s},-2)'"]


def _run_ffmpeg(args: list[str], duration: float,
                on_progress: Callable[[float], None]) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error",
           "-progress", "pipe:1", "-nostats", *args]
    with tempfile.TemporaryFile(mode="w+") as stderr:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=stderr, text=True)
        try:
            for line in proc.stdout:
                key, _, value = line.strip().partition("=")
                if key == "out_time_us" and value.isdigit():
                    on_progress(min(int(value) / 1e6 / duration, 1.0))
            proc.wait()
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        if proc.returncode != 0:
            stderr.seek(0)
            raise ShrinkError(f"ffmpeg failed: {stderr.read().strip()[-500:]}")


def encode(src: Path, dst: Path, info: MediaInfo, plan: EncodePlan, codec: str,
           progress: ProgressCallback) -> None:
    settings = CODEC_SETTINGS[codec]
    common = ["-i", str(src), "-map", "0:v:0", *settings["video"],
              "-b:v", f"{plan.video_kbps}k"]
    if plan.short_side:
        common += _scale_filter(plan.short_side)

    with tempfile.TemporaryDirectory(prefix="video-shrink-") as tmp:
        passlog = ["-passlogfile", str(Path(tmp) / "pass")]
        _run_ffmpeg(
            [*common, *settings["pass1"], "-pass", "1", *passlog,
             "-an", "-f", "null", "-"],
            info.duration,
            lambda f: progress(f / 2, "Analyzing (1/2)"),
        )
        audio = (["-map", "0:a:0", *settings["audio"], "-b:a", f"{plan.audio_kbps}k"]
                 if plan.audio_kbps else ["-an"])
        _run_ffmpeg(
            [*common, *settings["pass2"], "-pass", "2", *passlog, *audio,
             "-y", str(dst)],
            info.duration,
            lambda f: progress(0.5 + f / 2, "Encoding (2/2)"),
        )


def shrink(src: Path, preset: Preset, progress: ProgressCallback) -> Path | None:
    """Encode src to fit preset. Returns the output path, or None if src already fits."""
    if src.stat().st_size <= preset.target_bytes:
        return None
    info = probe(src)
    plan = plan_encode(info, preset.target_bytes, preset.audio_kbps)
    dst = output_path(src, preset)
    try:
        for attempt in range(MAX_RETRIES + 1):
            encode(src, dst, info, plan, preset.codec, progress)
            size = dst.stat().st_size
            if size <= preset.target_bytes:
                return dst
            if attempt == MAX_RETRIES:
                break
            # Overshot: scale the video bitrate down by the overshoot ratio.
            ratio = preset.target_bytes / size * 0.97
            plan = EncodePlan(int(plan.video_kbps * ratio), plan.audio_kbps,
                              plan.short_side)
        raise ShrinkError(f"could not fit within {preset.size_mb}MB")
    except BaseException:
        dst.unlink(missing_ok=True)
        raise

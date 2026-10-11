"""Load size presets from the bundled defaults and the user's config."""

from __future__ import annotations

import math
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PRESETS = Path(__file__).with_name("presets.toml")
CODECS = ("h264", "vp9")


def user_presets_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(config_home) / "nautilus-video-shrink" / "presets.toml"


@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    size_mb: float
    codec: str = "h264"
    audio_kbps: int = 96

    @property
    def target_bytes(self) -> int:
        return int(self.size_mb * 1_000_000)


class PresetError(ValueError):
    pass


def _parse(data: dict, source: Path) -> dict[str, Preset]:
    presets = {}
    for key, value in data.items():
        def fail(msg: str):
            raise PresetError(f"{source}: preset {key!r}: {msg}")

        if not isinstance(value, dict):
            fail("must be a table")
        codec = value.get("codec", "h264")
        if codec not in CODECS:
            fail(f"unknown codec {codec!r} (expected one of {', '.join(CODECS)})")
        size_mb = value.get("size_mb")
        if (not isinstance(size_mb, (int, float)) or isinstance(size_mb, bool)
                or not math.isfinite(size_mb) or size_mb <= 0):
            fail("size_mb must be a positive number")
        audio_kbps = value.get("audio_kbps", 96)
        if not isinstance(audio_kbps, int) or isinstance(audio_kbps, bool) or audio_kbps <= 0:
            fail("audio_kbps must be a positive integer")
        presets[key] = Preset(
            key=key,
            label=str(value.get("label", key)),
            size_mb=float(size_mb),
            codec=codec,
            audio_kbps=audio_kbps,
        )
    return presets


def _load_file(path: Path) -> dict[str, Preset]:
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise PresetError(f"{path}: {e}") from None
    return _parse(data, path)


def load_presets(user_path: Path | None = None) -> dict[str, Preset]:
    presets = _load_file(DEFAULT_PRESETS)
    user_path = user_path or user_presets_path()
    if user_path.is_file():
        presets.update(_load_file(user_path))
    return presets

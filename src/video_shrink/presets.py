"""Load size presets from the bundled defaults and the user's config."""

from __future__ import annotations

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


def _parse(data: dict) -> dict[str, Preset]:
    presets = {}
    for key, value in data.items():
        codec = value.get("codec", "h264")
        if codec not in CODECS:
            raise ValueError(f"preset {key!r}: unknown codec {codec!r}")
        presets[key] = Preset(
            key=key,
            label=value.get("label", key),
            size_mb=float(value["size_mb"]),
            codec=codec,
            audio_kbps=int(value.get("audio_kbps", 96)),
        )
    return presets


def load_presets(user_path: Path | None = None) -> dict[str, Preset]:
    with DEFAULT_PRESETS.open("rb") as f:
        presets = _parse(tomllib.load(f))
    user_path = user_path or user_presets_path()
    if user_path.is_file():
        with user_path.open("rb") as f:
            presets.update(_parse(tomllib.load(f)))
    return presets

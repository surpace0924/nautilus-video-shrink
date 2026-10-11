"""Nautilus context menu: Shrink Video > <preset>.

Installed to ~/.local/share/nautilus-python/extensions/ (requires python3-nautilus).
"""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from gi.repository import GObject, Nautilus

LIB_DIR = Path.home() / ".local/share/nautilus-video-shrink"
sys.path.insert(0, str(LIB_DIR))

from video_shrink.presets import load_presets  # noqa: E402


def _local_path(file_info):
    uri = urlparse(file_info.get_uri())
    return Path(unquote(uri.path)) if uri.scheme == "file" else None


class VideoShrinkMenuProvider(GObject.GObject, Nautilus.MenuProvider):
    def get_file_items(self, files):
        if not files or not all(f.get_mime_type().startswith("video/") for f in files):
            return []
        paths = [_local_path(f) for f in files]
        if None in paths:
            return []

        top = Nautilus.MenuItem(name="VideoShrink::Top", label="Shrink Video")
        submenu = Nautilus.Menu()
        top.set_submenu(submenu)
        # Reloaded on every popup so edits to presets.toml apply immediately.
        for preset in load_presets().values():
            item = Nautilus.MenuItem(name=f"VideoShrink::{preset.key}", label=preset.label)
            item.connect("activate", self._on_activate, preset.key, paths)
            submenu.append_item(item)
        return [top]

    def _on_activate(self, _item, preset_key, paths):
        env = dict(os.environ, PYTHONPATH=str(LIB_DIR))
        subprocess.Popen(
            ["python3", "-m", "video_shrink", "--gui", "--preset", preset_key,
             *map(str, paths)],
            env=env, start_new_session=True,
        )

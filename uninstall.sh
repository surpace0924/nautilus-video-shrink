#!/usr/bin/env bash
set -euo pipefail

rm -rf "$HOME/.local/share/nautilus-video-shrink"
rm -f "$HOME/.local/share/nautilus-python/extensions/video_shrink_menu.py"
rm -f "$HOME/.local/bin/video-shrink"

echo "Uninstalled. User presets in ~/.config/nautilus-video-shrink were kept."
echo "Restart Nautilus: nautilus -q"

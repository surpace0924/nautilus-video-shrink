#!/usr/bin/env bash
# Per-user install (no sudo needed except for missing apt packages).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB_DIR="$HOME/.local/share/nautilus-video-shrink"
EXT_DIR="$HOME/.local/share/nautilus-python/extensions"
BIN_DIR="$HOME/.local/bin"

missing=()
for pkg in ffmpeg python3-nautilus zenity libnotify-bin; do
    dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done
if ((${#missing[@]})); then
    echo "Missing packages: ${missing[*]}"
    echo "Install them with: sudo apt install ${missing[*]}"
    exit 1
fi

mkdir -p "$LIB_DIR" "$EXT_DIR" "$BIN_DIR"
rm -rf "$LIB_DIR/video_shrink"
cp -r "$REPO_DIR/src/video_shrink" "$LIB_DIR/"
cp "$REPO_DIR/nautilus/video_shrink_menu.py" "$EXT_DIR/"

cat >"$BIN_DIR/video-shrink" <<EOF
#!/bin/sh
PYTHONPATH="$LIB_DIR" exec python3 -m video_shrink "\$@"
EOF
chmod +x "$BIN_DIR/video-shrink"

echo "Installed. Restart Nautilus to load the menu: nautilus -q"

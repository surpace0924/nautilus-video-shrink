# nautilus-video-shrink

Right-click a video in Files (Nautilus) on Ubuntu, choose **Shrink Video** and a preset, and the video is re-encoded to fit within the preset's file size.

https://github.com/user-attachments/assets/ca88b455-11a6-49d9-948c-7edc3be9bb0a

- Presets for GitHub (10MB), Discord (20MB) and more
- Two-pass ffmpeg encoding to hit the target size (automatically re-encodes if it overshoots)
- Lowers the resolution automatically at low bitrates to keep the result watchable
- Output is saved next to the original as `<name>_<preset>.mp4` (H.264 presets) or `<name>_<preset>.webm` (VP9 presets); a numeric suffix is added if the name is taken

## Requirements

- Ubuntu 24.04 (GNOME / Nautilus 46)
- Python 3.12

## Installation

```sh
sudo apt install ffmpeg python3-nautilus zenity libnotify-bin
./install.sh
nautilus -q   # restart Nautilus to load the menu
```

To uninstall, run `./uninstall.sh`.

## Command-line usage

```sh
video-shrink --list-presets
video-shrink --preset github movie.mp4
```

## Custom presets

Presets defined in `~/.config/nautilus-video-shrink/presets.toml` are added to the defaults; a preset with the same key replaces the default one. See [src/video_shrink/presets.toml](src/video_shrink/presets.toml) for the format.

```toml
[discord]
label = "Discord (Nitro 500MB)"
size_mb = 500

[webm-8mb]
label = "WebM (8MB)"
size_mb = 8
codec = "vp9"   # VP9 + Opus (WebM)
```

## Codecs and patents

The default output is **H.264 + AAC (MP4)**, which has the widest playback support across Discord, GitHub, iOS and others.

H.264 and AAC are covered by patent pools (Via LA). This tool is **intended for personal, non-commercial use**.

- This project does not bundle or distribute any encoder; it only invokes the `ffmpeg` provided by your distribution.
- If you use it for commercial purposes, you are responsible for any H.264 / AAC patent licensing. In that case, consider presets using **VP9 + Opus (WebM)** (`codec = "vp9"`), which are generally regarded as royalty-free.

This section is not legal advice.

## Development

```sh
pytest
```

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

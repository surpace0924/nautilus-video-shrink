import pytest

from video_shrink.encoder import MediaInfo, ShrinkError, plan_encode
from video_shrink.presets import load_presets

MB = 1_000_000


def info(duration, width=1920, height=1080, has_audio=True):
    return MediaInfo(duration=duration, width=width, height=height, has_audio=has_audio)


def test_budget_fits_target():
    plan = plan_encode(info(60), 10 * MB, audio_kbps=96)
    total_bytes = (plan.video_kbps + plan.audio_kbps) * 1000 / 8 * 60
    assert total_bytes <= 10 * MB * 0.95


def test_short_clip_keeps_resolution():
    plan = plan_encode(info(10), 10 * MB, audio_kbps=96)
    assert plan.short_side is None


def test_long_clip_is_downscaled():
    plan = plan_encode(info(180), 10 * MB, audio_kbps=96)
    assert plan.short_side == 360


def test_portrait_never_upscaled():
    plan = plan_encode(info(10, width=320, height=568), 10 * MB, audio_kbps=96)
    assert plan.short_side is None


def test_no_audio_gives_all_bits_to_video():
    with_audio = plan_encode(info(60), 10 * MB, audio_kbps=96)
    without = plan_encode(info(60, has_audio=False), 10 * MB, audio_kbps=96)
    assert without.audio_kbps == 0
    assert without.video_kbps > with_audio.video_kbps


def test_too_long_raises():
    with pytest.raises(ShrinkError):
        plan_encode(info(3600), 10 * MB, audio_kbps=96)


def test_user_preset_overrides_default(tmp_path):
    user = tmp_path / "presets.toml"
    user.write_text('[discord]\nlabel = "Discord Nitro"\nsize_mb = 500\n'
                    '[webm]\nsize_mb = 8\ncodec = "vp9"\n')
    presets = load_presets(user)
    assert presets["discord"].size_mb == 500
    assert presets["webm"].codec == "vp9"
    assert "github" in presets

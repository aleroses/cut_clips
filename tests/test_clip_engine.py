"""Padding, argumentos de FFmpeg y caché de traducción, sin ejecutar cortes ni APIs."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.clip_engine import (
    _test_empty_gemini_translation_not_cached,
    build_single_pass_command,
    compute_padded_window,
    compute_padded_windows,
    cut_single_clip,
    load_translation_cache,
    lookup_cached_translation,
    normalize_translation_cache,
    save_translation_cache,
    translate_texts,
    validate_and_build_jobs,
)


def test_padding_clamps_to_zero_and_does_not_cross_neighbors():
    assert compute_padded_window(10.0, 12.0, padding_start=0.5, padding_end=0.5) == (
        9.5,
        12.5,
    )
    assert compute_padded_window(0.2, 1.0, padding_start=1.0, padding_end=0.0) == (
        0.0,
        1.0,
    )
    assert compute_padded_window(
        10.2,
        11.0,
        padding_start=1.0,
        padding_end=1.0,
        prev_end=10.0,
        next_start=11.4,
    ) == (10.0, 11.4)

    windows = compute_padded_windows(
        [
            {"start": 1.0, "end": 2.0, "text": "a"},
            {"start": 2.2, "end": 3.0, "text": "b"},
        ],
        padding=1.0,
    )
    assert windows == [(0.0, 2.2), (2.0, 4.0)]


def test_padding_can_invert_the_window_and_the_job_builder_rejects_it(tmp_path):
    start, end = compute_padded_window(
        10.0,
        10.2,
        padding_start=0.0,
        padding_end=0.0,
        next_start=9.0,
    )
    assert (start, end) == (10.0, 9.0)

    jobs, _rows, _video_skipped, _audio_skipped, invalid = validate_and_build_jobs(
        [{"start": 10.0, "end": 10.2, "text": "overlap"}],
        [(start, end)],
        "Example_Series",
        "S01E01",
        str(tmp_path),
        True,
        True,
        True,
    )
    assert jobs == []
    assert len(invalid) == 1
    assert invalid[0][0] == 1


def test_single_pass_command_is_a_list_and_keeps_paths_with_spaces():
    video_path = "videos/Episode One.mkv"
    webm_path = "out dir/Example_Series_S01E01_Line_0001.webm"
    mp3_path = "out dir/Example_Series_S01E01_Line_0001.mp3"
    cmd = build_single_pass_command(
        video_path,
        [
            {
                "index": 1,
                "start": 1.25,
                "end": 3.5,
                "need_video": True,
                "need_audio": True,
                "video_path": webm_path,
                "audio_path": mp3_path,
            }
        ],
        640,
        480,
        32,
        "96k",
        "128k",
        4.5,
        audio_track=1,
        video_track=0,
    )
    assert isinstance(cmd, list)
    assert all(isinstance(part, str) for part in cmd)
    assert cmd[:6] == ["ffmpeg", "-y", "-t", "4.500", "-i", video_path]
    assert webm_path in cmd
    assert mp3_path in cmd
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert isinstance(filter_complex, str)
    assert "[0:a:1]" in filter_complex
    assert "[0:v:0]" in filter_complex
    assert "trim=start=1.250:duration=2.250" in filter_complex
    assert "libvpx-vp9" in cmd
    assert "libmp3lame" in cmd
    assert cmd[-2:] == ["-loglevel", "error"]


def test_cut_single_clip_builds_list_arguments_without_running_ffmpeg():
    video_path = "videos/Episode One.mkv"
    output_base = "out dir/clip"
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return SimpleNamespace(returncode=0, stderr="")

    with patch("core.clip_engine.subprocess.run", side_effect=fake_run):
        ok, err = cut_single_clip(
            video_path,
            12.5,
            14.0,
            output_base,
            media="both",
            audio_track=1,
            video_track=0,
        )

    assert ok is True
    assert err == ""
    assert len(calls) == 2
    video_cmd, video_kwargs = calls[0]
    audio_cmd, audio_kwargs = calls[1]
    assert isinstance(video_cmd, list)
    assert isinstance(audio_cmd, list)
    assert video_kwargs.get("shell") is not True
    assert audio_kwargs.get("shell") is not True
    assert video_cmd[:6] == ["ffmpeg", "-y", "-ss", "2.500", "-i", video_path]
    assert video_cmd[-1] == output_base + ".webm"
    assert audio_cmd[-1] == output_base + ".mp3"
    assert "[0:v:0]" in video_cmd[video_cmd.index("-filter_complex") + 1]
    assert "[0:a:1]" in audio_cmd[audio_cmd.index("-filter_complex") + 1]


def test_translation_cache_normalizes_legacy_and_ignores_empty_values(tmp_path):
    assert normalize_translation_cache(None) == {"deepl": {}, "gemini": {}}
    assert normalize_translation_cache({"Hello": "Hola"}) == {
        "deepl": {"Hello": "Hola"},
        "gemini": {},
    }

    cache_path = tmp_path / "translations_cache.json"
    save_translation_cache(
        str(cache_path),
        {"deepl": {"Hello": "Hola", "Blank": ""}, "gemini": {}},
    )
    loaded = load_translation_cache(str(cache_path))
    assert loaded["deepl"]["Hello"] == "Hola"
    assert lookup_cached_translation(loaded, "deepl", "Hello") == "Hola"
    assert lookup_cached_translation(loaded, "deepl", "Blank") is None
    assert lookup_cached_translation(loaded, "deepl", "Missing") is None
    assert load_translation_cache(str(tmp_path / "absent.json")) == {
        "deepl": {},
        "gemini": {},
    }


def test_empty_deepl_translation_is_not_cached(tmp_path):
    cache_path = tmp_path / "translations_cache.json"
    sample = "Hello"
    save_translation_cache(str(cache_path), {"deepl": {sample: ""}, "gemini": {}})
    mock_deepl = MagicMock()
    mock_deepl.Translator.return_value.translate_text.return_value = [
        SimpleNamespace(text="  ")
    ]
    with patch.dict(sys.modules, {"deepl": mock_deepl}):
        results, failed = translate_texts([sample], "fake-key", "ES", str(cache_path))
    assert sample in failed
    assert results[sample] == ""
    assert sample not in load_translation_cache(str(cache_path))["deepl"]
    mock_deepl.Translator.assert_called_once_with("fake-key")


def test_empty_gemini_translation_is_not_cached():
    _test_empty_gemini_translation_not_cached()

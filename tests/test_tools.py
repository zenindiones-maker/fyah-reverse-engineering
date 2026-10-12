import json
import numpy as np
import pytest

SR = 22050


def click_track(bpm=120, dur=8.0, freq=440.0):
    t = np.arange(int(SR * dur)) / SR
    y = 0.2 * np.sin(2 * np.pi * freq * t)
    for b in np.arange(0, dur, 60 / bpm):
        i = int(b * SR); y[i:i + 400] += np.hanning(800)[400:] * 0.8
    return y.astype(np.float32)


def test_profile_tempo_and_loudness():
    from audio.profile import profile_signal
    p = profile_signal(click_track(120), SR)
    assert p["schema"] == "fyah-re/audio-profile@1"
    assert abs(p["tempo_bpm"] - 120) < 4 or abs(p["tempo_bpm"] - 60) < 2 or abs(p["tempo_bpm"] - 240) < 8
    assert p["loudness"]["integrated_lufs"] is not None
    assert sum(p["spectrum"]["band_energy"].values()) == pytest.approx(1, abs=0.05)


def test_key_detection_a_major_chord():
    from audio.profile import estimate_key
    t = np.arange(SR * 4) / SR
    y = sum(np.sin(2 * np.pi * f * t) for f in (220.0, 277.18, 329.63)).astype(np.float32)
    k = estimate_key(y, SR)
    assert k["tonic"] in ("A", "C#", "F#") and k["mode"] in ("major", "minor")


def test_profile_file_roundtrip(tmp_path):
    import soundfile as sf
    from audio.profile import main
    f = tmp_path / "x.wav"; sf.write(f, np.stack([click_track(), click_track()], 1), SR)
    out = tmp_path / "p.json"
    assert main([str(f), "--out", str(out)]) == 0
    p = json.loads(out.read_text()); assert p["channels"] == 2 and "stereo" in p


def test_compare_detects_loudness_and_tempo():
    from audio.compare import compare_signals, to_markdown
    a, b = click_track(120), click_track(90) * 0.25
    d = compare_signals(a, SR, b, SR)
    assert d["loudness_lufs"]["delta"] > 6
    assert d["tempo_bpm"]["delta"] != 0
    assert "Comparação" in to_markdown(d)
    same = compare_signals(a, SR, a, SR)
    assert same["timbre_mfcc_cosine"] == pytest.approx(1, abs=1e-6) and same["mel_curve_distance_db"] == 0


def test_pacing_metrics():
    from video.pacing import pacing_from_cuts
    p = pacing_from_cuts([2, 4, 6, 15], 20.0, window_s=10)
    assert p["cuts"] == 4 and p["shots"] == 5 and p["cuts_per_minute"] == 12.0
    assert p["cuts_per_window"] == [3, 1] and p["shot_length_s"]["max"] == 9


def test_pacing_on_synthetic_video(tmp_path):
    cv2 = pytest.importorskip("cv2")
    from video.pacing import detect_cuts, pacing_from_cuts
    f = str(tmp_path / "v.mp4")
    w = cv2.VideoWriter(f, cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    rng = np.random.default_rng(0)
    for k in range(4):
        base = rng.integers(0, 255, (48, 64, 3), dtype=np.uint8)
        for _ in range(20):
            w.write(base)
    w.release()
    cuts, dur = detect_cuts(f)
    p = pacing_from_cuts(cuts, dur)
    assert p["cuts"] == 3 and abs(dur - 8) < 0.5


def test_apk_markdown():
    from apps.apk import to_markdown
    d = {"app_name": "X", "package": "a.b", "version_name": "1", "version_code": "1", "min_sdk": "21", "target_sdk": "34",
         "size_bytes": 10, "dex_files": ["classes.dex"], "native_abis": [], "permissions": ["android.permission.RECORD_AUDIO"],
         "activities": [], "services": [], "receivers": [], "providers": []}
    md = to_markdown(d)
    assert "a.b" in md and "RECORD_AUDIO" in md


def test_silence_does_not_invent_a_key_or_tempo():
    from audio.profile import profile_signal
    p = profile_signal(np.zeros(SR * 2, dtype=np.float32), SR)
    assert p["tempo_bpm"] == 0.0
    assert p["beats"] == 0
    assert p["key"]["estimable"] is False
    assert p["key"]["tonic"] is None
    assert p["loudness"]["integrated_lufs"] is None
    assert any("silêncio" in item for item in p["limitations"])


def test_short_audio_does_not_invent_tempo():
    from audio.profile import profile_signal
    n = int(SR * 0.2)
    y = (0.2 * np.sin(2 * np.pi * 440 * np.arange(n) / SR)).astype(np.float32)
    p = profile_signal(y, SR)
    assert p["duration_s"] == pytest.approx(0.2, abs=0.02)
    assert p["tempo_bpm"] == 0.0
    assert p["key"]["estimable"] is False
    assert any("curto" in item for item in p["limitations"])

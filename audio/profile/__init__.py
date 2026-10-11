"""Perfil de faixa de áudio: BPM, tonalidade, loudness (LUFS) e espectro em JSON."""
from __future__ import annotations

import numpy as np

KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# Perfis de Krumhansl-Kessler (valores publicados, domínio público científico)
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def load(path: str, sr: int = 22050):
    import librosa
    y, sr = librosa.load(path, sr=sr, mono=False)
    return y, sr


def estimate_key(mono: np.ndarray, sr: int) -> dict:
    import librosa
    chroma = librosa.feature.chroma_cqt(y=mono, sr=sr).mean(axis=1)
    best = (-2.0, "C", "major")
    for i in range(12):
        for mode, prof in (("major", MAJOR), ("minor", MINOR)):
            r = float(np.corrcoef(chroma, np.roll(prof, i))[0, 1])
            if r > best[0]:
                best = (r, KEYS[i], mode)
    return {"tonic": best[1], "mode": best[2], "confidence": round(best[0], 3)}


def profile_signal(y: np.ndarray, sr: int) -> dict:
    import librosa
    import pyloudnorm as pyln
    stereo = y.ndim == 2
    mono = librosa.to_mono(y) if stereo else y
    dur = len(mono) / sr
    tempo, beats = librosa.beat.beat_track(y=mono, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    data = y.T if stereo else mono
    meter = pyln.Meter(sr, block_size=min(0.4, max(dur / 2, 0.05)))
    try:
        lufs = float(meter.integrated_loudness(data))
    except Exception:
        lufs = float("nan")
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    rms = float(np.sqrt(np.mean(mono ** 2))) if mono.size else 0.0
    S = np.abs(librosa.stft(mono, n_fft=2048))
    centroid = float(librosa.feature.spectral_centroid(S=S, sr=sr).mean())
    rolloff = float(librosa.feature.spectral_rolloff(S=S, sr=sr).mean())
    flatness = float(librosa.feature.spectral_flatness(S=S).mean())
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    power = (S ** 2).mean(axis=1)
    bands = {"sub": (0, 60), "low": (60, 250), "low_mid": (250, 2000), "high_mid": (2000, 6000), "high": (6000, sr / 2)}
    tot = power.sum() or 1.0
    band_energy = {k: round(float(power[(freqs >= a) & (freqs < b)].sum() / tot), 4) for k, (a, b) in bands.items()}
    mfcc = librosa.feature.mfcc(y=mono, sr=sr, n_mfcc=13).mean(axis=1)
    out = {
        "schema": "fyah-re/audio-profile@1",
        "duration_s": round(dur, 3),
        "sample_rate": sr,
        "channels": 2 if stereo else 1,
        "tempo_bpm": round(tempo, 2),
        "beats": int(len(beats)),
        "key": estimate_key(mono, sr),
        "loudness": {
            "integrated_lufs": None if np.isnan(lufs) or np.isinf(lufs) else round(lufs, 2),
            "peak_dbfs": round(20 * np.log10(peak), 2) if peak > 0 else None,
            "rms_dbfs": round(20 * np.log10(rms), 2) if rms > 0 else None,
            "crest_db": round(20 * np.log10(peak / rms), 2) if rms > 0 else None,
        },
        "spectrum": {"centroid_hz": round(centroid, 1), "rolloff_hz": round(rolloff, 1),
                     "flatness": round(flatness, 5), "band_energy": band_energy},
        "timbre": {"mfcc_mean": [round(float(v), 3) for v in mfcc]},
    }
    if stereo:
        l, r = y[0], y[1]
        corr = float(np.corrcoef(l, r)[0, 1]) if np.std(l) > 0 and np.std(r) > 0 else 1.0
        out["stereo"] = {"lr_correlation": round(corr, 3)}
    return out


def profile_file(path: str) -> dict:
    y, sr = load(path)
    p = profile_signal(y, sr)
    p["source"] = str(path).rsplit("/", 1)[-1]
    return p


def main(argv=None) -> int:
    import argparse, json, pathlib
    ap = argparse.ArgumentParser(prog="python -m audio.profile")
    ap.add_argument("audio"); ap.add_argument("--out")
    a = ap.parse_args(argv)
    res = json.dumps(profile_file(a.audio), indent=2, ensure_ascii=False)
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True); pathlib.Path(a.out).write_text(res)
    print(res)
    return 0

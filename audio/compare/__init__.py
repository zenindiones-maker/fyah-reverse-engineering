"""Comparador de faixas: diferenças de tempo, tonalidade, loudness, espectro e timbre."""
from __future__ import annotations

import numpy as np

from audio.profile import load, profile_signal


def _mel_db(mono, sr):
    import librosa
    m = librosa.feature.melspectrogram(y=mono, sr=sr, n_mels=64)
    return librosa.power_to_db(m.mean(axis=1) + 1e-10)


def compare_signals(ya, sra, yb, srb) -> dict:
    import librosa
    pa, pb = profile_signal(ya, sra), profile_signal(yb, srb)
    ma = librosa.to_mono(ya) if ya.ndim == 2 else ya
    mb = librosa.to_mono(yb) if yb.ndim == 2 else yb
    mel_a, mel_b = _mel_db(ma, sra), _mel_db(mb, srb)
    mel_a -= mel_a.max(); mel_b -= mel_b.max()
    fa, fb = np.array(pa["timbre"]["mfcc_mean"]), np.array(pb["timbre"]["mfcc_mean"])
    cos = float(fa @ fb / (np.linalg.norm(fa) * np.linalg.norm(fb) + 1e-12))
    la, lb = pa["loudness"]["integrated_lufs"], pb["loudness"]["integrated_lufs"]
    d = {
        "schema": "fyah-re/audio-compare@1",
        "tempo_bpm": {"a": pa["tempo_bpm"], "b": pb["tempo_bpm"], "delta": round(pa["tempo_bpm"] - pb["tempo_bpm"], 2)},
        "key": {"a": pa["key"], "b": pb["key"], "same": pa["key"]["tonic"] == pb["key"]["tonic"] and pa["key"]["mode"] == pb["key"]["mode"]},
        "loudness_lufs": {"a": la, "b": lb, "delta": None if la is None or lb is None else round(la - lb, 2)},
        "crest_db_delta": None if pa["loudness"]["crest_db"] is None or pb["loudness"]["crest_db"] is None else round(pa["loudness"]["crest_db"] - pb["loudness"]["crest_db"], 2),
        "spectral_centroid_delta_hz": round(pa["spectrum"]["centroid_hz"] - pb["spectrum"]["centroid_hz"], 1),
        "band_energy_delta": {k: round(pa["spectrum"]["band_energy"][k] - pb["spectrum"]["band_energy"][k], 4) for k in pa["spectrum"]["band_energy"]},
        "mel_curve_distance_db": round(float(np.mean(np.abs(mel_a - mel_b))), 2),
        "timbre_mfcc_cosine": round(cos, 4),
        "profiles": {"a": pa, "b": pb},
    }
    return d


def to_markdown(d: dict) -> str:
    L = ["## Comparação de faixas (A vs B)", "", "| Métrica | A | B | Δ |", "|---|---|---|---|",
         f"| BPM | {d['tempo_bpm']['a']} | {d['tempo_bpm']['b']} | {d['tempo_bpm']['delta']} |",
         f"| Tonalidade | {d['key']['a']['tonic']} {d['key']['a']['mode']} | {d['key']['b']['tonic']} {d['key']['b']['mode']} | {'igual' if d['key']['same'] else 'diferente'} |",
         f"| LUFS | {d['loudness_lufs']['a']} | {d['loudness_lufs']['b']} | {d['loudness_lufs']['delta']} |",
         f"| Crest (dB) | | | {d['crest_db_delta']} |",
         f"| Centroide espectral (Hz) | | | {d['spectral_centroid_delta_hz']} |",
         f"| Distância da curva mel (dB) | | | {d['mel_curve_distance_db']} |",
         f"| Similaridade de timbre (cos MFCC) | | | {d['timbre_mfcc_cosine']} |", "", "Energia por banda (Δ A−B): " +
         ", ".join(f"{k} {v:+.3f}" for k, v in d["band_energy_delta"].items())]
    return "\n".join(L) + "\n"


def compare_files(a: str, b: str) -> dict:
    ya, sra = load(a); yb, srb = load(b)
    return compare_signals(ya, sra, yb, srb)


def main(argv=None) -> int:
    import argparse, json, pathlib
    ap = argparse.ArgumentParser(prog="python -m audio.compare")
    ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("--out"); ap.add_argument("--md")
    x = ap.parse_args(argv)
    d = compare_files(x.a, x.b)
    for p, txt in ((x.out, json.dumps(d, indent=2, ensure_ascii=False)), (x.md, to_markdown(d))):
        if p:
            pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True); pathlib.Path(p).write_text(txt)
    print(to_markdown(d))
    return 0

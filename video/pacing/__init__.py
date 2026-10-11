"""Analisador de cortes e ritmo de edição (PySceneDetect + métricas de pacing)."""
from __future__ import annotations

import csv
import statistics


def _sec(t):
    return t.seconds if hasattr(type(t), "seconds") else t.get_seconds()


def detect_cuts(video: str, threshold: float = 27.0) -> tuple[list[float], float]:
    """Retorna (tempos dos cortes em s, duração em s) usando PySceneDetect (BSD-3)."""
    from scenedetect import ContentDetector, detect, open_video
    v = open_video(video)
    dur = _sec(v.duration)
    scenes = detect(video, ContentDetector(threshold=threshold))
    cuts = [_sec(s[0]) for s in scenes[1:]]
    if scenes:
        dur = max(dur, _sec(scenes[-1][1]))
    return cuts, dur


def pacing_from_cuts(cuts: list[float], duration: float, window_s: float = 10.0) -> dict:
    cuts = sorted(c for c in cuts if 0 < c < duration)
    bounds = [0.0] + cuts + [duration]
    shots = [round(b - a, 3) for a, b in zip(bounds, bounds[1:]) if b > a]
    n_win = max(1, int(-(-duration // window_s)))
    curve = [0] * n_win
    for c in cuts:
        curve[min(int(c // window_s), n_win - 1)] += 1
    return {
        "schema": "fyah-re/video-pacing@1",
        "duration_s": round(duration, 3),
        "cuts": len(cuts),
        "shots": len(shots),
        "cuts_per_minute": round(len(cuts) / (duration / 60), 2) if duration > 0 else 0.0,
        "shot_length_s": {
            "mean": round(statistics.mean(shots), 3) if shots else 0.0,
            "median": round(statistics.median(shots), 3) if shots else 0.0,
            "min": min(shots) if shots else 0.0,
            "max": max(shots) if shots else 0.0,
            "stdev": round(statistics.pstdev(shots), 3) if shots else 0.0,
        },
        "window_s": window_s,
        "cuts_per_window": curve,
        "cut_times_s": [round(c, 3) for c in cuts],
    }


def cuts_from_scenes_csv(path: str) -> tuple[list[float], float]:
    """Lê o CSV do `scenedetect list-scenes`."""
    rows = list(csv.reader(open(path, newline="")))
    hdr_i = next(i for i, r in enumerate(rows) if r and r[0].startswith("Scene Number"))
    h = rows[hdr_i]
    si, ei = h.index("Start Time (seconds)"), h.index("End Time (seconds)")
    data = [r for r in rows[hdr_i + 1:] if r]
    starts = [float(r[si]) for r in data]
    return starts[1:], float(data[-1][ei]) if data else 0.0


def main(argv=None) -> int:
    import argparse, json, pathlib
    ap = argparse.ArgumentParser(prog="python -m video.pacing")
    ap.add_argument("input", help="vídeo ou CSV do scenedetect list-scenes")
    ap.add_argument("--threshold", type=float, default=27.0)
    ap.add_argument("--window", type=float, default=10.0)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    cuts, dur = cuts_from_scenes_csv(a.input) if a.input.endswith(".csv") else detect_cuts(a.input, a.threshold)
    res = json.dumps(pacing_from_cuts(cuts, dur, a.window), indent=2)
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True); pathlib.Path(a.out).write_text(res)
    print(res)
    return 0

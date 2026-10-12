"""Pipelines combinados do E.R.: encadeiam as ferramentas já instaladas. Saída JSON + Markdown."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys


def _run_module(mod: str, *args: str) -> None:
    subprocess.run([sys.executable, "-m", mod, *args], check=True)


def audio_full(audio: str, outdir: str, venvs: str | None = None) -> dict:
    """profile → beats(beat_this) → notas(basic-pitch via venv) → stems(demucs) → perfil por stem."""
    out = pathlib.Path(outdir); out.mkdir(parents=True, exist_ok=True)
    from audio.profile import profile_file
    res: dict = {"schema": "fyah-re/audio-full@1", "source": pathlib.Path(audio).name}
    res["profile"] = profile_file(audio)
    (out / "profile.json").write_text(json.dumps(res["profile"], indent=2, ensure_ascii=False))
    try:
        from beat_this.inference import File2Beats
        beats, downs = File2Beats(checkpoint_path="final0", device="cpu", dbn=False)(audio)
        res["beats"] = {"beats": len(beats), "downbeats": len(downs)}
    except Exception as e:  # noqa: BLE001
        res["beats"] = {"error": str(e)[:160]}
    if venvs:
        bp = pathlib.Path(venvs) / "basicpitch" / "bin" / "python"
        if bp.exists():
            code = ("import pathlib,basic_pitch,json,sys;from basic_pitch.inference import Model,predict;"
                    "o=pathlib.Path(basic_pitch.__file__).parent/'saved_models'/'icassp_2022'/'nmp.onnx';"
                    "_,m,n=predict(sys.argv[1],Model(o));print(len(n))")
            r = subprocess.run([str(bp), "-c", code, audio], capture_output=True, text=True)
            res["notes"] = {"count": int(r.stdout.strip() or 0)} if r.returncode == 0 else {"error": r.stderr.strip()[-160:]}
    try:
        subprocess.run([sys.executable, "-m", "demucs", "-n", "htdemucs", "-o", str(out), "--mp3", audio], check=True)
        stems_dir = next((out / "htdemucs").glob("*"))
        res["stems"] = {}
        for s in sorted(stems_dir.glob("*.mp3")):
            p = profile_file(str(s))
            res["stems"][s.stem] = {"tempo_bpm": p["tempo_bpm"], "lufs": p["loudness"]["integrated_lufs"],
                                     "centroid_hz": p["spectrum"]["centroid_hz"]}
            (out / f"stem_{s.stem}.json").write_text(json.dumps(p, indent=2, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        res["stems"] = {"error": str(e)[:160]}
    (out / "audio_full.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


def video_full(video: str, outdir: str) -> dict:
    out = pathlib.Path(outdir); out.mkdir(parents=True, exist_ok=True)
    res: dict = {"schema": "fyah-re/video-full@1", "source": pathlib.Path(video).name}
    r = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", video],
                       capture_output=True, text=True)
    res["ffprobe"] = json.loads(r.stdout) if r.returncode == 0 else {"error": r.stderr[-160:]}
    from video.pacing import detect_cuts, pacing_from_cuts
    cuts, dur = detect_cuts(video)
    res["pacing"] = pacing_from_cuts(cuts, dur)
    try:
        import av, numpy as np
        c = av.open(video); frames = []
        for i, f in enumerate(c.decode(video=0)):
            if i % 15 == 0:
                frames.append(np.asarray(f.to_image()).reshape(-1, 3).mean(0))
            if len(frames) >= 40:
                break
        import colour  # noqa: F401
        arr = np.array(frames) / 255.0
        res["color"] = {"mean_rgb": arr.mean(0).round(3).tolist(), "frames_sampled": len(frames)}
    except Exception as e:  # noqa: BLE001
        res["color"] = {"error": str(e)[:160]}
    # legendas embutidas (faixas de texto), se houver
    rs = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "s", "-show_entries",
                         "stream=index:stream_tags=language", "-of", "json", video], capture_output=True, text=True)
    try:
        res["subtitles"] = {"text_tracks": len(json.loads(rs.stdout).get("streams", []))}
    except Exception:  # noqa: BLE001
        res["subtitles"] = {"text_tracks": 0}
    (out / "video_full.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


def apk_full(apk: str, outdir: str) -> dict:
    out = pathlib.Path(outdir); out.mkdir(parents=True, exist_ok=True)
    from apps.apk import inspect_apk
    res: dict = {"schema": "fyah-re/apk-full@1"}
    res["androguard"] = inspect_apk(apk)
    import shutil
    if shutil.which("jadx"):
        jd = out / "jadx"
        subprocess.run(["jadx", "-q", "-d", str(jd), apk], capture_output=True)
        res["jadx"] = {"java_files": sum(1 for _ in jd.rglob("*.java"))}
    if shutil.which("apktool"):
        ad = out / "apktool"
        subprocess.run(["apktool", "d", "-q", "-f", "-o", str(ad), apk], capture_output=True)
        res["apktool"] = {"smali_files": sum(1 for _ in ad.rglob("*.smali")), "decoded": ad.exists()}
    if shutil.which("d2j-dex2jar.sh"):
        jar = out / "app.jar"
        subprocess.run(["d2j-dex2jar.sh", "-f", "-o", str(jar), apk], capture_output=True)
        res["dex2jar"] = {"jar_bytes": jar.stat().st_size if jar.exists() else 0}
    if shutil.which("quark"):
        qout = out / "quark.json"
        r = subprocess.run(["quark", "-a", apk, "-o", str(qout)], capture_output=True, text=True, timeout=300)
        res["quark"] = {"rc": r.returncode, "report": qout.exists()}
    (out / "apk_full.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


def probe_disassembler(path: str) -> dict:
    """Run rizin or radare2, or record that neither binary is available."""
    import shutil
    if shutil.which("rz-bin"):
        completed = subprocess.run(["rz-bin", "-I", "-j", path], capture_output=True, text=True)
        if completed.returncode != 0:
            return {"available": True, "tool": "rz-bin", "error": f"rz-bin exit {completed.returncode}", "stderr": completed.stderr[:300]}
        try:
            return {"available": True, "tool": "rz-bin", "info": json.loads(completed.stdout)}
        except json.JSONDecodeError:
            return {"available": True, "tool": "rz-bin", "error": "saída não JSON", "raw": completed.stdout[:500]}
    if shutil.which("r2"):
        completed = subprocess.run(["r2", "-qq", "-c", "iIj", path], capture_output=True, text=True)
        if completed.returncode != 0:
            return {"available": True, "tool": "r2", "error": f"r2 exit {completed.returncode}", "stderr": completed.stderr[:300]}
        try:
            return {"available": True, "tool": "r2", "info": json.loads(completed.stdout)}
        except json.JSONDecodeError:
            return {"available": True, "tool": "r2", "error": "saída não JSON", "raw": completed.stdout[:500]}
    return {"available": False, "error": "rz-bin e r2 ausentes no PATH"}


def binary_inspect(path: str, outdir: str) -> dict:
    """radare2/rizin + capa + FLOSS + file magic — só arquivos próprios/autorizados."""
    out = pathlib.Path(outdir); out.mkdir(parents=True, exist_ok=True)
    res: dict = {"schema": "fyah-re/binary-inspect@1", "source": pathlib.Path(path).name}
    import shutil, magic
    res["magic"] = magic.from_file(path)
    res["rizin"] = probe_disassembler(path)
    if shutil.which("capa"):
        r = subprocess.run(["capa", "-q", "-j", path], capture_output=True, text=True, timeout=300)
        try: res["capa"] = {"rules": len(json.loads(r.stdout).get("rules", {}))}
        except Exception: res["capa"] = {"rc": r.returncode}
    if shutil.which("floss"):
        r = subprocess.run(["floss", "-q", path], capture_output=True, text=True, timeout=300)
        strings = [ln for ln in r.stdout.splitlines() if ln.strip()]
        res["floss"] = {"strings": len(strings), "sample": strings[:10]}
    (out / "binary_inspect.json").write_text(json.dumps(res, indent=2, ensure_ascii=False))
    return res


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m pipelines")
    ap.add_argument("pipeline", choices=["audio-full", "video-full", "apk-full", "binary-inspect"])
    ap.add_argument("input"); ap.add_argument("--out", default="out"); ap.add_argument("--venvs")
    a = ap.parse_args(argv)
    fn = {"audio-full": lambda: audio_full(a.input, a.out, a.venvs),
          "video-full": lambda: video_full(a.input, a.out),
          "apk-full": lambda: apk_full(a.input, a.out),
          "binary-inspect": lambda: binary_inspect(a.input, a.out)}[a.pipeline]
    print(json.dumps(fn(), indent=2, ensure_ascii=False)[:2000])
    return 0


if __name__ == "__main__":
    import sys as _s
    _s.exit(main())

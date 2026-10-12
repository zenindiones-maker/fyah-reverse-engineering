"""CLI uniforme: list | run | smoke."""
from __future__ import annotations

import argparse, json, pathlib, subprocess, sys, tempfile, urllib.request

from tools.catalog import CATALOG, by_name, list_for_prompt


def download(url: str, dest: pathlib.Path) -> pathlib.Path:
    if url.startswith(("http://", "https://")):
        req = urllib.request.Request(url, headers={"User-Agent": "fyah-re-tools"})
        dest.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        return dest
    p = pathlib.Path(url)
    if not p.exists():
        raise SystemExit(f"arquivo não encontrado: {url}")
    return p


def run_tool(name: str, inputs: list[str], out: pathlib.Path) -> dict:
    if name not in by_name:
        raise SystemExit(f"ferramenta desconhecida: {name}")
    t = by_name[name]
    expected_inputs = t.get("inputs", 1)
    if len(inputs) != expected_inputs:
        if name == "compare":
            raise SystemExit("compare exige --input e --input2")
        raise SystemExit(f"{name} exige {expected_inputs} entrada(s); recebeu {len(inputs)}")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="fyah-tool-"))
    paths = [download(u, tmp / f"in{i}") for i, u in enumerate(inputs)]
    kind = t.get("kind") or "module"

    if kind == "shell" and name == "media-inspect":
        r = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(paths[0])],
                           capture_output=True, text=True, check=True)
        data = {"schema": "fyah-re/media-inspect@1", "ok": True, "ffprobe": json.loads(r.stdout)}
        mi = subprocess.run(["mediainfo", "--Output=JSON", str(paths[0])], capture_output=True, text=True)
        if mi.returncode == 0:
            data["mediainfo"] = json.loads(mi.stdout)
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return data

    if kind == "stems":
        wav = tmp / "a.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(paths[0]), str(wav)], check=True)
        odir = out.parent / "stems"
        subprocess.run([sys.executable, "-m", "demucs", "-n", "htdemucs", "-o", str(odir), "--mp3", str(wav)], check=True)
        files = sorted(str(p) for p in odir.rglob("*.mp3"))
        data = {"schema": "fyah-re/stems@1", "ok": True, "stems": files}
        out.write_text(json.dumps(data, indent=2)); return data

    if kind == "silero_vad":
        import torch, torchaudio
        model, utils = torch.hub.load(repo_or_dir="snakers4/silero-vad", model="silero_vad", trust_repo=True)
        (get_speech_timestamps, _, read_audio, *_) = utils
        wav = read_audio(str(paths[0]), sampling_rate=16000)
        ts = get_speech_timestamps(wav, model, sampling_rate=16000)
        data = {"schema": "fyah-re/silero-vad@1", "ok": True, "segments": len(ts), "timestamps": ts[:50]}
        out.write_text(json.dumps(data, indent=2)); return data

    if kind == "supervision":
        import supervision as sv, numpy as np
        xyxy = np.array([[10, 10, 50, 50]], dtype=float)
        det = sv.Detections(xyxy=xyxy, confidence=np.array([0.9]), class_id=np.array([0]))
        data = {"schema": "fyah-re/supervision@1", "ok": True, "version": sv.__version__, "detections": len(det)}
        out.write_text(json.dumps(data, indent=2)); return data

    if t.get("module") == "pipelines":
        subprocess.run([sys.executable, "-m", "pipelines", *t["argv"], str(paths[0]), "--out", str(out.parent)], check=True)
        produced = out.parent / (name.replace("-", "_") + ".json")
        if produced.exists():
            data = json.loads(produced.read_text())
            data.setdefault("ok", True)
            out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            return data
        raise SystemExit("pipeline sem JSON de saída")

    cmd = [sys.executable, "-m", t["module"], *[str(p) for p in paths], "--out", str(out)]
    subprocess.run(cmd, check=True)
    data = json.loads(out.read_text())
    data.setdefault("ok", True)
    return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fyah-re")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("prompt")
    r = sub.add_parser("run")
    r.add_argument("name"); r.add_argument("--input", required=True); r.add_argument("--input2")
    r.add_argument("--out", required=True)
    s = sub.add_parser("smoke"); s.add_argument("--name", default="media-inspect")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        print(json.dumps(CATALOG, indent=2, ensure_ascii=False)); return 0
    if a.cmd == "prompt":
        print(list_for_prompt()); return 0
    if a.cmd == "smoke":
        if a.name not in by_name:
            raise SystemExit(f"ferramenta desconhecida: {a.name}")
        if a.name == "media-inspect":
            url = "https://upload.wikimedia.org/wikipedia/commons/4/40/Toreador_song_cleaned.ogg"
            out = pathlib.Path(tempfile.mkdtemp()) / "smoke.json"
            d = run_tool(a.name, [url], out)
            print(json.dumps({"ok": d.get("ok", True), "name": a.name, "keys": list(d)[:8]})); return 0
        print(json.dumps({"ok": True, "name": a.name, "skipped": "no default sample"})); return 0
    inputs = [a.input] + ([a.input2] if a.input2 else [])
    d = run_tool(a.name, inputs, pathlib.Path(a.out))
    print(json.dumps({"ok": d.get("ok", True), "out": a.out, "schema": d.get("schema")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

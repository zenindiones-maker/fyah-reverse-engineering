"""Roteador do workflow er-analyze: executa a ferramenta/pipeline e escreve o resumo do job."""
import json, os, pathlib, shutil, subprocess, sys

tool, inp, inp2 = sys.argv[1], sys.argv[2], sys.argv[3]
out = pathlib.Path("out"); out.mkdir(exist_ok=True)
summary = open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a")
py = sys.executable


def run(*a):
    subprocess.run(list(a), check=True)


def table(rows, head):
    return "| " + " | ".join(head) + " |\n|" + "---|" * len(head) + "\n" + "".join("| " + " | ".join(map(str, r)) + " |\n" for r in rows)


if tool in ("audio-full", "stems") or tool.startswith("audio"):
    wav = "input.wav"; run("ffmpeg", "-loglevel", "error", "-y", "-i", inp, wav); inp = wav

if tool == "audio-profile":
    run(py, "-m", "audio.profile", inp, "--out", "out/profile.json")
    d = json.load(open("out/profile.json"))
    summary.write("## Perfil de áudio\n\n" + table([[d["tempo_bpm"], f"{d['key']['tonic']} {d['key']['mode']}", d["loudness"]["integrated_lufs"], d["duration_s"]]], ["BPM", "Tonalidade", "LUFS", "Duração (s)"]))
elif tool == "compare":
    run(py, "-m", "audio.compare", inp, inp2, "--out", "out/compare.json", "--md", "out/compare.md")
    summary.write(open("out/compare.md").read())
elif tool == "media-inspect":
    r = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", inp], capture_output=True, text=True, check=True)
    (out / "ffprobe.json").write_text(r.stdout)
    (out / "mediainfo.json").write_text(subprocess.run(["mediainfo", "--Output=JSON", inp], capture_output=True, text=True).stdout)
    d = json.loads(r.stdout); f = d["format"]
    summary.write(f"## Inspeção de mídia\n\nContainer: **{f.get('format_long_name')}** · duração {f.get('duration')} s · bitrate {f.get('bit_rate')}\n\n")
    summary.write(table([[s["index"], s.get("codec_type"), s.get("codec_name"), s.get("sample_rate") or f"{s.get('width')}x{s.get('height')}"] for s in d["streams"]], ["#", "tipo", "codec", "detalhe"]))
elif tool == "cuts-pacing":
    run(py, "-m", "video.pacing", inp, "--out", "out/pacing.json")
    d = json.load(open("out/pacing.json"))
    summary.write(f"## Cortes e ritmo\n\nCortes: {d['cuts']} · cortes/min: {d['cuts_per_minute']} · plano médio: {d['shot_length_s']['mean']} s\n")
elif tool == "stems":
    run(py, "-m", "demucs", "-n", "htdemucs", "-o", "out", "--mp3", inp)
    summary.write("## Stems (htdemucs, CPU)\n\n" + "\n".join(f"- {p.name}" for p in sorted(out.rglob("*.mp3"))) + "\n")
elif tool == "apk-inspect":
    run(py, "-m", "apps.apk", inp, "--out", "out/apk.json", "--md", "out/apk.md")
    summary.write(open("out/apk.md").read())
elif tool == "binary-inspect":
    run(py, "-m", "pipelines", "binary-inspect", inp, "--out", "out")
    d = json.load(open("out/binary_inspect.json"))
    summary.write(f"## Binary inspect\n\nMagic: `{d.get('magic')}`\n\n")
    if "capa" in d: summary.write(f"capa rules: {d['capa']}\n")
    if "floss" in d: summary.write(f"FLOSS strings: {d['floss'].get('strings')}\n")
elif tool in ("audio-full", "video-full", "apk-full"):
    venvs = str(pathlib.Path.home() / ".er-venvs")
    run(py, "-m", "pipelines", tool, inp, "--out", "out", "--venvs", venvs)
    d = json.load(open(f"out/{tool.replace('-', '_')}.json"))
    summary.write(f"## Pipeline {tool}\n\n")
    if tool == "audio-full":
        p = d["profile"]
        summary.write(table([[p["tempo_bpm"], f"{p['key']['tonic']} {p['key']['mode']}", p["loudness"]["integrated_lufs"], d.get("beats"), d.get("notes")]], ["BPM", "Tonalidade", "LUFS", "beat_this", "notas (basic-pitch)"]))
        if isinstance(d.get("stems"), dict) and "error" not in d["stems"]:
            summary.write("\n" + table([[k, v["tempo_bpm"], v["lufs"], v["centroid_hz"]] for k, v in d["stems"].items()], ["stem", "BPM", "LUFS", "centroide Hz"]))
    elif tool == "video-full":
        pc = d["pacing"]
        summary.write(table([[pc["cuts"], pc["cuts_per_minute"], pc["shot_length_s"]["mean"], d["color"].get("mean_rgb"), d["subtitles"]["text_tracks"]]], ["cortes", "cortes/min", "plano médio (s)", "RGB médio", "faixas de legenda"]))
    else:
        a = d["androguard"]
        summary.write(table([[a["package"], a["version_name"], len(a["permissions"]), d.get("jadx", {}).get("java_files"), d.get("apktool", {}).get("smali_files")]], ["pacote", "versão", "permissões", ".java (jadx)", ".smali (apktool)"]))
else:
    sys.exit(f"ferramenta desconhecida: {tool}")

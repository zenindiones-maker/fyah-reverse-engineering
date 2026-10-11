# Kaggle (GPU grátis, ~30 h/semana): separação Demucs htdemucs_ft. Saída em /kaggle/working (vira o output do kernel).
# A URL de entrada é injetada pelo workflow er-gpu-kaggle em job_input.json. Só material próprio/licenciado/domínio público.
import json, os, subprocess, sys, urllib.request

cfg = json.load(open("job_input.json")) if os.path.exists("job_input.json") else {}
url = cfg.get("url") or "https://upload.wikimedia.org/wikipedia/commons/4/40/Toreador_song_cleaned.ogg"
model = cfg.get("model", "htdemucs_ft")
os.chdir("/kaggle/working")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "demucs"], check=True)
req = urllib.request.Request(url, headers={"User-Agent": "fyah-re-kaggle"})
open("input_raw", "wb").write(urllib.request.urlopen(req).read())
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", "input_raw", "input.wav"], check=True)
subprocess.run([sys.executable, "-m", "demucs", "-n", model, "-d", "cuda", "--mp3", "-o", "stems", "input.wav"], check=True)
os.remove("input_raw"); os.remove("input.wav")
json.dump({"model": model, "source": url, "stems": sorted(os.listdir(f"stems/{model}/input"))}, open("result.json", "w"), indent=2)
print(open("result.json").read())

"""Smoke test de cada ferramenta do E.R. (versão/ajuda + chamada real mínima). Gera docs/ferramentas/STATUS.md.

Sem API, sem token, sem cadastro. Amostras: sinais sintéticos e um APK open source (F-Droid, GPL) baixado anonimamente.
"""
from __future__ import annotations

import datetime, os, pathlib, shutil, subprocess, sys, tempfile, time, traceback, urllib.request, json

T = pathlib.Path(tempfile.mkdtemp(prefix="er-tc-"))
WAV, MP4, APK = T / "s.wav", T / "v.mp4", T / "a.apk"
RESULTS: list[tuple] = []


def sh(cmd: str, timeout=300) -> str:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-300:])
    return (r.stdout or r.stderr).strip()


def check(area, name, fn):
    t = time.time()
    try:
        info = (str(fn() or "ok").strip().splitlines() or ["ok"])[0][:110]
        RESULTS.append((area, name, "✅", info, round(time.time() - t, 1)))
    except Exception as e:  # noqa: BLE001
        msg = (str(e) or type(e).__name__).replace("\n", " ")[:160]
        RESULTS.append((area, name, "❌", msg, round(time.time() - t, 1)))
    print(RESULTS[-1], flush=True)


def ver(mod):
    import importlib
    m = importlib.import_module(mod)
    return getattr(m, "__version__", getattr(m, "VERSION", "importado"))


def prepare():
    import numpy as np, soundfile as sf
    sr = 22050; t = np.arange(sr * 4) / sr
    y = 0.3 * np.sin(2 * np.pi * 220 * t) * (1 + 0.5 * (np.sin(2 * np.pi * 2 * t) > 0))
    sf.write(WAV, y.astype("float32"), sr)
    if shutil.which("ffmpeg"):
        sh(f"ffmpeg -loglevel error -y -f lavfi -i testsrc=d=2:s=160x120:r=10 -f lavfi -i color=red:d=2:s=160x120:r=10 "
           f"-filter_complex '[0][1]concat=n=2:v=1' {MP4}")
    try:
        pkg = "org.billthefarmer.tuner"
        req = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "fyah-re-toolcheck"}), timeout=60).read()
        vc = json.loads(req(f"https://f-droid.org/api/v1/packages/{pkg}"))["suggestedVersionCode"]
        APK.write_bytes(req(f"https://f-droid.org/repo/{pkg}_{vc}.apk"))
    except Exception as e:  # noqa: BLE001
        print("APK de amostra indisponível:", e)


# ---------------- áudio ----------------
def librosa_():
    import librosa
    y, sr = librosa.load(WAV); tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    return f"librosa {librosa.__version__}, beat_track ok"

def pyloudnorm_():
    import pyloudnorm as pyln, soundfile as sf
    y, sr = sf.read(WAV); return f"LUFS {pyln.Meter(sr).integrated_loudness(y):.1f}"

def essentia_():
    import essentia.standard as es
    a = es.MonoLoader(filename=str(WAV))(); bpm = es.RhythmExtractor2013()(a)[0]
    import essentia; return f"essentia {essentia.__version__}, RhythmExtractor ok"

def pedalboard_():
    import pedalboard, soundfile as sf
    y, sr = sf.read(WAV, dtype="float32")
    out = pedalboard.Pedalboard([pedalboard.Compressor(), pedalboard.Reverb()])(y, sr)
    return f"pedalboard {pedalboard.__version__}, {len(out)} amostras processadas"

def audioflux_():
    import audioflux as af, soundfile as sf
    y, sr = sf.read(WAV, dtype="float32"); spec, _ = af.mel_spectrogram(y, samplate=sr)
    return f"audioflux {af.__version__}, mel {spec.shape}"

def matchering_():
    import matchering as mg
    return f"matchering {mg.__version__} (import)"

def music21_():
    import music21; s = music21.stream.Stream([music21.note.Note("C4"), music21.note.Note("E4"), music21.note.Note("G4")])
    return f"music21 {music21.__version__}, key {s.analyze('key')}"

def pywt_():
    import pywt, numpy as np; cA, cD = pywt.dwt(np.arange(16.0), "db1"); return f"pywt {pywt.__version__}"

def audiomentations_():
    import audiomentations as A, numpy as np
    A.Gain(p=1.0)(samples=np.zeros(1000, "float32"), sample_rate=16000); return f"audiomentations {A.__version__}"

def mir_eval_():
    import mir_eval, numpy as np; f = mir_eval.beat.f_measure(np.array([1.0, 2.0]), np.array([1.0, 2.0])); return f"mir_eval {mir_eval.__version__}, F={f}"

def miditok_():
    import miditok; return f"miditok {ver('miditok')}"

def mirdata_():
    import mirdata; return f"mirdata {mirdata.__version__}, {len(mirdata.list_datasets())} datasets"

def torchaudio_():
    import torch, torchaudio; w = torch.zeros(1, 16000); torchaudio.transforms.MelSpectrogram()(w)
    return f"torch {torch.__version__} / torchaudio {torchaudio.__version__} (CPU)"

def demucs_():
    import demucs; from demucs.pretrained import get_model
    return f"demucs {demucs.__version__} (import; pesos públicos baixados só no workflow stems)"

VENVS = pathlib.Path.home() / ".er-venvs"


def iso(venv: str, code: str, timeout=900) -> str:
    py = VENVS / venv / "bin" / "python"
    if not py.exists():
        raise RuntimeError(f"venv {venv} não instalada")
    env = {**os.environ, "WAV": str(WAV), "MP4": str(MP4), "T": str(T)}
    r = subprocess.run([str(py), "-c", code], capture_output=True, text=True, timeout=timeout, env=env)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1][-200:])
    return r.stdout.strip().splitlines()[-1]

def basic_pitch_():
    return iso("basicpitch", """
import os, pathlib, basic_pitch
from basic_pitch.inference import Model, predict
onnx = pathlib.Path(basic_pitch.__file__).parent / 'saved_models' / 'icassp_2022' / 'nmp.onnx'
_, midi, notes = predict(os.environ['WAV'], Model(onnx))
print(f'basic-pitch (ONNX, venv isolada): {len(notes)} notas')""")

def beat_this_():
    from beat_this.inference import File2Beats
    beats, down = File2Beats(checkpoint_path="final0", device="cpu", dbn=False)(str(WAV))
    return f"beat_this: {len(beats)} beats, {len(down)} downbeats"

def torchcrepe_():
    import torch, torchcrepe, soundfile as sf
    y, sr = sf.read(WAV, dtype="float32")
    f0 = torchcrepe.predict(torch.tensor(y)[None], sr, 160, 50, 1000, "tiny", device="cpu", batch_size=512)
    return f"torchcrepe tiny: f0 mediano {float(f0.median()):.0f} Hz (esperado ~220)"

def dawdreamer_():
    import dawdreamer as daw, soundfile as sf
    y, sr = sf.read(WAV, dtype="float32")
    eng = daw.RenderEngine(sr, 512); pb = eng.make_playback_processor("pb", y[None].repeat(2, 0))
    eng.load_graph([(pb, [])]); eng.render(1.0)
    return f"DawDreamer {daw.__version__ if hasattr(daw,'__version__') else ''}: render {eng.get_audio().shape}"

def asteroid_():
    return iso("asteroid", """
import torch, asteroid
from asteroid.models import ConvTasNet
m = ConvTasNet(n_src=2).eval()
with torch.no_grad(): out = m(torch.randn(1, 8000))
print(f'asteroid {asteroid.__version__}: ConvTasNet forward {tuple(out.shape)} (pesos aleatórios)')""")

def spleeter_():
    return iso("spleeter", """
import os, subprocess, sys, pathlib
import tarfile, urllib.request
out = pathlib.Path(os.environ['T']) / 'spl'
mp = pathlib.Path(os.environ['T']) / 'pretrained_models'; md = mp / '2stems'
if not (md / '.probe').exists():  # pesos públicos da release oficial v1.4.0 (download anônimo)
    md.mkdir(parents=True, exist_ok=True)
    tgz = mp / '2stems.tar.gz'
    urllib.request.urlretrieve('https://github.com/deezer/spleeter/releases/download/v1.4.0/2stems.tar.gz', tgz)
    tarfile.open(tgz).extractall(md); (md / '.probe').write_text('OK')
os.environ['MODEL_PATH'] = str(mp)
r = subprocess.run([str(pathlib.Path(sys.executable).parent / 'spleeter'), 'separate', '-p', 'spleeter:2stems', '-o', str(out), os.environ['WAV']], capture_output=True, text=True)
if r.returncode: raise SystemExit('spleeter: ' + (r.stderr or r.stdout).strip().splitlines()[-1][-180:])
print('spleeter 2stems: ' + ', '.join(sorted(p.name for p in out.rglob('*.wav'))))""", timeout=1200)

def allin1_():
    return iso("allin1", """
import os, allin1
r = allin1.analyze(os.environ['WAV'], device='cpu', keep_byproducts=False)
print(f'allin1: BPM {r.bpm}, {len(r.beats)} beats, {len(r.segments)} segmentos')""", timeout=1800)

def transnet_():
    return iso("transnet", """
import os, torch
from transnetv2_pytorch import TransNetV2
m = TransNetV2(); m.eval()
r = m.detect_scenes(os.environ['MP4']) if hasattr(m,'detect_scenes') else None
print(f'TransNetV2 (pytorch): {len(r) if r is not None else "modelo carregado"} cenas')""")

def fyah_profile_():
    from audio.profile import profile_file; p = profile_file(str(WAV)); return f"fyah audio.profile BPM {p['tempo_bpm']}"


# ---------------- lote 1 (áudio) ----------------
def pretty_midi_():
    import pretty_midi; pm = pretty_midi.PrettyMIDI(); inst = pretty_midi.Instrument(0)
    inst.notes.append(pretty_midi.Note(100, 60, 0, 0.5)); pm.instruments.append(inst); p = T / "x.mid"; pm.write(str(p))
    return f"pretty_midi: MIDI {pretty_midi.PrettyMIDI(str(p)).get_end_time():.1f}s"
def mido_():
    import mido; return f"mido {mido.__version__}: {len(mido.MidiFile(T / 'x.mid').tracks)} trilha(s)"
def muspy_():
    import muspy; m = muspy.read_midi(T / "x.mid"); return f"muspy {muspy.__version__}: {len(m.tracks)} trilha(s)"
def partitura_():
    import partitura as pt; perf = pt.load_performance_midi(str(T / "x.mid")); return f"partitura {pt.__version__ if hasattr(pt,'__version__') else ''}: {len(perf.note_array())} nota(s)"
def resampy_():
    import resampy, soundfile as sf; y, sr = sf.read(WAV); z = resampy.resample(y, sr, 16000); return f"resampy: {len(y)}→{len(z)} amostras"
def nnaudio_():
    import torch; from nnAudio import features; import soundfile as sf
    y, sr = sf.read(WAV, dtype="float32"); spec = features.CQT(sr=sr, verbose=False)(torch.tensor(y)[None]); return f"nnAudio CQT {tuple(spec.shape)}"
def chromaprint_():
    import acoustid; dur, fp = acoustid.fingerprint_file(str(WAV)); return f"chromaprint/fpcalc: fingerprint {len(fp)} bytes, {dur:.1f}s (local, sem lookup)"
def nussl_():
    return iso("nussl", """
import os, nussl
sig = nussl.AudioSignal(os.environ['WAV']); r = nussl.separation.primitive.HPSS(sig)(); print(f'nussl {nussl.__version__}: HPSS {len(r)} fontes')""")
def msaf_():
    return iso("msaf", """
import os, msaf
b, l = msaf.process(os.environ['WAV'], boundaries_id='sf', labels_id='fmc2d'); print(f'msaf {msaf.__version__}: {len(b)} fronteiras')""", timeout=900)

# ---------------- vídeo ----------------
def ffmpeg_(): return sh("ffmpeg -version")
def ffprobe_(): return sh(f"ffprobe -v error -show_entries format=duration -of csv=p=0 {MP4}") + " s (ffprobe)"
def mediainfo_(): return sh("mediainfo --Version").splitlines()[-1]
def pymediainfo_():
    from pymediainfo import MediaInfo; mi = MediaInfo.parse(str(MP4)); return f"pymediainfo: {len(mi.tracks)} trilhas"
def scenedetect_():
    from video.pacing import detect_cuts; cuts, d = detect_cuts(str(MP4)); return f"PySceneDetect: {len(cuts)} corte(s) em {d:.1f}s"
def colour_():
    import colour, numpy as np; lab = colour.XYZ_to_Lab(colour.sRGB_to_XYZ(np.array([1.0, 0, 0]))); return f"colour {colour.__version__}, Lab vermelho {lab.round(1).tolist()}"
def av_():
    import av; c = av.open(str(MP4)); n = sum(1 for _ in c.decode(video=0)); return f"PyAV {av.__version__}, {n} frames"


# ---------------- lote 2 (vídeo/apps) + lote 3 (formatos/binários/ML) ----------------
def ffmpy_():
    import ffmpy; return f"ffmpy {getattr(ffmpy,'__version__','importado')}"
def pillow_():
    from PIL import Image; import numpy as np
    Image.fromarray(np.zeros((8,8,3),np.uint8)).save(T/"x.png"); return f"Pillow {Image.__version__}: PNG 8x8"
def plotbitrate_():
    # CLI leve: plotbitrate do pip (zeroepoch/plotbitrate)
    try: return "plotbitrate " + sh("plotbitrate --version")
    except Exception:
        import importlib.util
        if importlib.util.find_spec("plotbitrate"): return "plotbitrate importado"
        raise
def apkleaks_():
    r = subprocess.run(["apkleaks", "-f", str(APK), "-o", str(T/"apkleaks.json")], capture_output=True, text=True, timeout=300)
    return f"apkleaks: rc={r.returncode}, saída {(T/'apkleaks.json').exists()}"
def objection_():
    return "objection " + sh("objection version")
def magika_():
    from magika import Magika; r = Magika().identify_path(APK if APK.exists() else WAV); return f"magika: {r.output.ct_label}"
def olefile_():
    import olefile; return f"olefile {olefile.__version__} (import)"
def exifread_():
    import exifread; return f"exifread {exifread.__version__} (import)"
def onnx_():
    import onnx; m = onnx.helper.make_model(onnx.helper.make_graph([], "g", [], [])); onnx.checker.check_model(m); return f"onnx {onnx.__version__}: modelo vazio ok"
def onnxruntime_():
    import onnxruntime as ort; return f"onnxruntime {ort.__version__}: {ort.get_available_providers()}"
def onnxsim_():
    import onnxsim; return f"onnxsim {getattr(onnxsim,'__version__',ver('onnxsim'))}"
def netron_():
    import netron; return f"netron {netron.__version__} (import; servidor/visualização sob demanda)"
def angr_():
    import angr; p = angr.Project(SAMPLE_BIN, auto_load_libs=False); return f"angr {angr.__version__}: entry {hex(p.entry)}"
def unicorn_():
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_64; Uc(UC_ARCH_X86, UC_MODE_64); import unicorn; return f"unicorn {unicorn.__version__}: x86_64"
def keystone_():
    from keystone import Ks, KS_ARCH_X86, KS_MODE_64; e, _ = Ks(KS_ARCH_X86, KS_MODE_64).asm(b"nop"); return f"keystone: {bytes(e).hex()}"
def pywhat_():
    return "pyWhat " + sh("pywhat --version").splitlines()[0]
def yara_():
    import yara; r = yara.compile(source='rule x { strings: $a="ELF" condition: $a }'); m = r.match(data=open(SAMPLE_BIN,"rb").read()); return f"yara-python: matches={len(m)}"
def scapy_():
    from scapy.all import IP, TCP; p = IP()/TCP(); return f"scapy: pacote {p.summary()}"

# ---------------- apps ----------------
def androguard_():
    from apps.apk import inspect_apk; d = inspect_apk(str(APK)); return f"androguard: {d['package']} v{d['version_name']}, {len(d['permissions'])} permissões"
def jadx_():
    out = T / "jadx"; sh(f"jadx -q -d {out} {APK}", timeout=600)
    n = sum(1 for _ in out.rglob("*.java")); return f"jadx {sh('jadx --version')}: {n} arquivos .java"
def apktool_():
    sh(f"apktool d -q -f -o {T/'apktool'} {APK}", timeout=600); return f"apktool {sh('apktool --version')}: decodificado"
def frida_():
    return f"frida-tools {sh('frida --version')} (sem alvo: só versão)"

# ---------------- formatos ----------------
def kaitai_():
    import kaitaistruct; return f"kaitaistruct runtime {kaitaistruct.__version__}"
def construct_():
    import construct as c; return f"construct {c.version_string if hasattr(c,'version_string') else ver('construct')}: " + str(c.Struct('a' / c.Int16ub).parse(b'\x00\x05').a)
def hachoir_():
    from hachoir.parser import createParser
    p = createParser(str(WAV)); return f"hachoir: {p.description if p else 'sem parser'}"
def magic_():
    import magic; return "libmagic: " + magic.from_file(str(APK if APK.exists() else WAV))

# ---------------- binários ----------------
SAMPLE_BIN = "/bin/ls"
def radare2_(): return sh("r2 -v").splitlines()[0]
def r2pipe_():
    import r2pipe; r = r2pipe.open(SAMPLE_BIN, flags=["-2"]); info = r.cmdj("ij"); r.quit(); return f"r2pipe: {info['bin']['arch']} {info['bin']['bits']} bits"
def capstone_():
    import capstone; md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
    return "capstone " + capstone.__version__ + ": " + " ; ".join(f"{i.mnemonic} {i.op_str}" for i in md.disasm(b"\x55\x48\x89\xe5\xc3", 0))
def lief_():
    import lief; b = lief.parse(SAMPLE_BIN); return f"lief {lief.__version__}: {len(b.sections)} seções"
def pefile_():
    import pefile; return f"pefile {pefile.__version__} (import)"
def pyelftools_():
    from elftools.elf.elffile import ELFFile; e = ELFFile(open(SAMPLE_BIN, "rb")); return f"pyelftools: {e.num_sections()} seções"
def ghidra_():
    home = os.environ.get("GHIDRA_HOME")
    if not home: raise RuntimeError("GHIDRA_HOME ausente")
    proj = T / "gproj"; proj.mkdir(exist_ok=True)
    out = sh(f"{home}/support/analyzeHeadless {proj} p -import {SAMPLE_BIN} -noanalysis -deleteProject 2>&1 | tail -3", timeout=900)
    return "Ghidra headless: import ok " + pathlib.Path(home).name


CHECKS_EXTRA = {
    "modelos_ml": [("onnx", onnx_), ("onnxruntime", onnxruntime_), ("onnxsim", onnxsim_), ("netron", netron_)],
    "protocolos": [("scapy", scapy_)],
}
CHECKS = {
    "audio": [("librosa", librosa_), ("pyloudnorm", pyloudnorm_), ("essentia", essentia_), ("pedalboard", pedalboard_),
              ("audioflux", audioflux_), ("matchering", matchering_), ("music21", music21_), ("PyWavelets", pywt_),
              ("audiomentations", audiomentations_), ("mir_eval", mir_eval_), ("miditok", miditok_), ("mirdata", mirdata_),
              ("torchaudio (CPU)", torchaudio_), ("demucs", demucs_), ("basic-pitch", basic_pitch_), ("beat_this", beat_this_), ("torchcrepe", torchcrepe_), ("DawDreamer", dawdreamer_), ("asteroid", asteroid_), ("spleeter", spleeter_), ("allin1", allin1_), ("pretty_midi", pretty_midi_), ("mido", mido_), ("muspy", muspy_), ("partitura", partitura_), ("resampy", resampy_), ("nnAudio", nnaudio_), ("chromaprint (fpcalc)", chromaprint_), ("nussl", nussl_), ("msaf", msaf_), ("fyah audio.profile", fyah_profile_)],
    "video": [("ffmpeg", ffmpeg_), ("ffprobe", ffprobe_), ("mediainfo", mediainfo_), ("pymediainfo", pymediainfo_),
              ("PySceneDetect", scenedetect_), ("TransNetV2", transnet_), ("colour-science", colour_), ("PyAV", av_), ("ffmpy", ffmpy_), ("Pillow", pillow_)],
    "apps": [("androguard", androguard_), ("jadx", jadx_), ("apktool", apktool_), ("frida-tools", frida_), ("apkleaks", apkleaks_), ("objection", objection_)],
    "formatos": [("kaitaistruct", kaitai_), ("construct", construct_), ("hachoir", hachoir_), ("python-magic", magic_), ("magika", magika_), ("olefile", olefile_), ("exifread", exifread_)],
    "binarios": [("radare2", radare2_), ("r2pipe", r2pipe_), ("capstone", capstone_), ("lief", lief_), ("pefile", pefile_),
                 ("pyelftools", pyelftools_), ("Ghidra headless", ghidra_), ("angr", angr_), ("unicorn", unicorn_), ("keystone", keystone_), ("pyWhat", pywhat_), ("yara-python", yara_)],
}


def main():
    prepare()
    for area, items in {**CHECKS, **CHECKS_EXTRA}.items():
        for name, fn in items:
            check(area, name, fn)
    ok = sum(r[2] == "✅" for r in RESULTS)
    L = [f"# Status das ferramentas do E.R.", "",
         f"Gerado por `er-toolcheck` em {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M} UTC no runner `ubuntu-latest` (CPU). "
         f"**{ok}/{len(RESULTS)} OK.** Sem API, sem token, sem cadastro.", "",
         "| Área | Ferramenta | Status | Detalhe | s |", "|---|---|---|---|---|"]
    L += [f"| {a} | {n} | {s} | {d.replace('|', '/')} | {t} |" for a, n, s, d, t in RESULTS]
    txt = "\n".join(L) + "\n"
    p = pathlib.Path(__file__).resolve().parent.parent / "docs" / "ferramentas" / "STATUS.md"
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(txt)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(txt)
    print(txt)


if __name__ == "__main__":
    main()

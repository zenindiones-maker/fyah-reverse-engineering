"""Catálogo uniforme: cada ferramenta tem name, área, versão, invocação e smoke.

Contrato:
  python -m tools run <name> --input <path|URL> [--input2 ...] --out <json>
  Saída JSON com schema fyah-re/<name>@N + campo "ok".
"""
from __future__ import annotations

CATALOG: list[dict] = [
    # pipelines
    {"name": "audio-full", "area": "pipeline", "version": "1", "module": "pipelines", "argv": ["audio-full"], "needs": ["audio", "ml"], "desc": "perfil+beats+notas+stems"},
    {"name": "video-full", "area": "pipeline", "version": "1", "module": "pipelines", "argv": ["video-full"], "needs": ["video"], "desc": "inspect+cortes+cor+legendas"},
    {"name": "apk-full", "area": "pipeline", "version": "1", "module": "pipelines", "argv": ["apk-full"], "needs": ["apps"], "desc": "androguard+jadx+apktool"},
    {"name": "binary-inspect", "area": "pipeline", "version": "1", "module": "pipelines", "argv": ["binary-inspect"], "needs": ["binary"], "desc": "magic+rizin+capa+floss"},
    # core
    {"name": "audio-profile", "area": "audio", "version": "1", "module": "audio.profile", "argv": [], "needs": ["audio"], "desc": "BPM/key/LUFS/espectro"},
    {"name": "compare", "area": "audio", "version": "1", "module": "audio.compare", "argv": [], "needs": ["audio"], "inputs": 2, "desc": "compara duas faixas"},
    {"name": "media-inspect", "area": "video", "version": "1", "kind": "shell", "needs": [], "desc": "ffprobe+mediainfo"},
    {"name": "cuts-pacing", "area": "video", "version": "1", "module": "video.pacing", "argv": [], "needs": ["video"], "desc": "cortes e ritmo"},
    {"name": "apk-inspect", "area": "apps", "version": "1", "module": "apps.apk", "argv": [], "needs": ["apps"], "desc": "manifesto APK"},
    {"name": "stems", "area": "audio", "version": "1", "kind": "stems", "needs": ["ml"], "desc": "Demucs htdemucs CPU"},
    {"name": "fingerprint", "area": "audio", "version": "1", "module": "audio.fingerprint", "argv": [], "needs": [], "desc": "Chromaprint/fpcalc local, sem lookup"},
    # util batch
    {"name": "silero-vad", "area": "audio", "version": "1", "kind": "silero_vad", "needs": ["ml"], "desc": "VAD Silero (torch hub)"},
    {"name": "supervision-detect", "area": "video", "version": "1", "kind": "supervision", "needs": ["video"], "desc": "bloqueado até integrar detector real e pesos de modelo"},
]

by_name = {t["name"]: t for t in CATALOG}

def list_for_prompt() -> str:
    lines = ["Ferramentas disponíveis (rode via: python -m tools run NOME --input ARQUIVO --out out.json):", ""]
    for t in CATALOG:
        lines.append(f"- {t['name']} [{t['area']}] — {t['desc']}")
    lines += ["", "Regras: só material próprio/licenciado/domínio público; sem DRM; saída sempre JSON."]
    return "\n".join(lines)

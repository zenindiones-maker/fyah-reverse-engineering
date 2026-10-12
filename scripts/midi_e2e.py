"""Prova E2E da transcrição MIDI. O WAV nasce aqui; o dispatcher é o caminho real."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from audio.midi_transcribe import match_reference, parse_midi_notes, write_reference_wav


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )


def _silence(path: Path) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(22050)
        wav.writeframes(b"\x00\x00" * 22050 * 2)


def _failed(path: Path, result: subprocess.CompletedProcess[str]) -> dict:
    if result.returncode == 0 or path.exists() or path.with_suffix(".mid").exists():
        raise SystemExit(f"caso negativo produziu sucesso: {path.name}\n{result.stderr}")
    receipt_path = path.parent / (path.name + ".receipt.json")
    receipt = json.loads(receipt_path.read_text())
    if receipt["status"] == "success" or receipt["output_artifacts"]:
        raise SystemExit(f"recibo de sucesso indevido: {receipt}")
    return receipt


def main() -> None:
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    source = out / "reference.wav"
    write_reference_wav(source)
    output = out / "midi.json"
    result = _run(["run", "midi-transcribe", "--input", str(source), "--out", str(output)])
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(f"transcrição falhou: {result.returncode}")
    payload = json.loads(output.read_text())
    midi = out / "midi.mid"
    if payload["schema"] != "fyah-re/midi-transcribe@1" or payload["ok"] is not True:
        raise SystemExit("JSON de transcrição inválido")
    if payload["tool_version"] != "0.4.0" or payload["model"]["sha256"] != "2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec":
        raise SystemExit("proveniência do modelo divergente")
    detected = parse_midi_notes(midi)
    pairs = match_reference(detected)
    receipt = json.loads((out / "midi.json.receipt.json").read_text())
    if receipt["status"] != "success":
        raise SystemExit("recibo não é success")
    artifacts = {item["path"]: item["sha256"] for item in receipt["output_artifacts"]}
    for name in ("midi.json", "midi.mid"):
        digest = hashlib.sha256((out / name).read_bytes()).hexdigest()
        if artifacts.get(name) != digest:
            raise SystemExit(f"SHA-256 divergente em {name}: {artifacts.get(name)} != {digest}")
    missing = _failed(out / "missing.json", _run(["run", "midi-transcribe", "--input", str(out / "nao-existe.wav"), "--out", str(out / "missing.json")]))
    corrupt = out / "corrupt.wav"
    corrupt.write_bytes(b"not a wav")
    corrupt_receipt = _failed(out / "corrupt.json", _run(["run", "midi-transcribe", "--input", str(corrupt), "--out", str(out / "corrupt.json")]))
    silence = out / "silence.wav"
    _silence(silence)
    silence_receipt = _failed(out / "silence.json", _run(["run", "midi-transcribe", "--input", str(silence), "--out", str(out / "silence.json")]))
    report = {
        "sha": os.environ.get("GITHUB_SHA"),
        "branch_head_note": "pull_request jobs check out the merge commit; headSha of the run is the branch",
        "tool": payload["tool"],
        "tool_version": payload["tool_version"],
        "license": payload["license"],
        "model_sha256": payload["model"]["sha256"],
        "note_count": len(detected),
        "matches": pairs,
        "tolerances": {"pitch_semitones": 1, "onset_s": 0.08, "offset_s": 0.08},
        "receipt_sha256": artifacts,
        "negative": {
            "missing": missing["status"],
            "corrupt": corrupt_receipt["status"],
            "silence": silence_receipt["status"],
        },
        "limitations": payload["limitations"],
    }
    (out / "midi-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print("midi e2e ok", json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()

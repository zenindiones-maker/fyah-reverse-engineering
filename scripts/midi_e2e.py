"""Matriz MIDI A–F pelo dispatcher. B e D registram a falha; não a escondem."""
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

from audio.midi_transcribe import (
    PINNED_MODEL_SHA256,
    MidiError,
    case_specs,
    evaluate_notes,
    parse_midi_notes,
    render_wav,
    verify_model,
)


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _silence(path: Path) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(22050)
        wav.writeframes(b"\x00\x00" * 22050 * 2)


def _require_failed(path: Path, result: subprocess.CompletedProcess[str]) -> dict:
    if result.returncode == 0 or path.exists() or path.with_suffix(".mid").exists():
        raise SystemExit(f"caso negativo produziu sucesso: {path.name}\n{result.stderr}")
    receipt = json.loads((path.parent / (path.name + ".receipt.json")).read_text())
    if receipt["status"] == "success" or receipt["output_artifacts"]:
        raise SystemExit(f"recibo de sucesso indevido: {receipt}")
    return receipt


def _positive(out: Path, spec: dict) -> dict:
    wav = out / f"{spec['id']}.wav"
    render_wav(wav, spec["notes"], spec["tail_s"])
    output = out / f"{spec['id']}.json"
    result = _run(["run", "midi-transcribe", "--input", str(wav), "--out", str(output)])
    (out / f"{spec['id']}.log").write_text(result.stdout + "\n" + result.stderr)
    if result.returncode != 0:
        raise SystemExit(f"caso {spec['id']} não transcreveu: {result.returncode}\n{result.stderr}")
    payload = json.loads(output.read_text())
    midi = out / f"{spec['id']}.mid"
    detected = parse_midi_notes(midi)
    score = evaluate_notes(detected, spec["notes"], spec["partials"])
    receipt = json.loads((out / f"{spec['id']}.json.receipt.json").read_text())
    artifacts = {item["path"]: item["sha256"] for item in receipt["output_artifacts"]}
    for name in (output.name, midi.name):
        if artifacts.get(name) != _sha256(out / name):
            raise SystemExit(f"SHA-256 divergente em {name}")
    if receipt["status"] != "success" or payload["model"]["sha256"] != PINNED_MODEL_SHA256:
        raise SystemExit(f"caso {spec['id']} sem recibo ou modelo fixado")
    if score["status"] != spec["expect"]:
        raise SystemExit(f"caso {spec['id']} classificou {score['status']}, referência prévia era {spec['expect']}: {score}")
    if spec["id"] == "B" and 88 not in {item["pitch"] for item in score["harmonic_confusions"]}:
        raise SystemExit(f"a oitava extra não foi reproduzida: {score}")
    if spec["id"] == "D" and 97 not in {item["pitch"] for item in score["harmonic_confusions"]}:
        raise SystemExit(f"o parcial MIDI 97 não foi reproduzido: {score}")
    return {
        "id": spec["id"],
        "title": spec["title"],
        "status": score["status"],
        "expected_status": spec["expect"],
        "detected": [
            {"pitch": note["pitch"], "start_s": round(note["start_s"], 6), "end_s": round(note["end_s"], 6)}
            for note in detected
        ],
        "matched": score["matched"],
        "missing": score["missing"],
        "harmonic_confusions": score["harmonic_confusions"],
        "unrelated_extras": score["unrelated_extras"],
        "known_partials": [
            {"name": item["name"], "pitch": item["pitch"], "start_s": item["start_s"], "duration_s": item["duration_s"]}
            for item in spec["partials"]
        ],
        "receipt_sha256": artifacts,
        "model_sha256": payload["model"]["sha256"],
        "parameters": payload["parameters"],
    }


def _reject_corrupt_model() -> None:
    python = Path(os.environ["FYAH_RE_VENVS"]) / "basicpitch" / "bin" / "python"
    probe = r'''
import basic_pitch, pathlib, sys
sys.path.insert(0, %r)
from audio.midi_transcribe import MidiError, verify_model, PINNED_MODEL_SHA256
model = pathlib.Path(basic_pitch.__file__).parent / "saved_models" / "icassp_2022" / "nmp.onnx"
assert verify_model(model, "0.4.0") == PINNED_MODEL_SHA256
bad = pathlib.Path("/tmp/nmp-divergente.onnx")
raw = bytearray(model.read_bytes())
raw[-1] ^= 0xFF
bad.write_bytes(raw)
try:
    verify_model(bad, "0.4.0")
except MidiError as exc:
    if "divergente" not in str(exc):
        raise SystemExit(str(exc))
else:
    raise SystemExit("hash divergente foi aceito")
print("hash rejeitado antes de qualquer inferência")
''' % str(ROOT)
    result = subprocess.run([str(python), "-c", probe], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)
    print(result.stdout.strip())


def main() -> None:
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    _reject_corrupt_model()
    specs = case_specs()
    cases = [_positive(out, specs[name]) for name in ("A", "B", "C", "D", "E")]
    negatives = {
        "missing": _require_failed(out / "missing.json", _run(["run", "midi-transcribe", "--input", str(out / "nao-existe.wav"), "--out", str(out / "missing.json")])),
        "corrupt": _require_failed(out / "corrupt.json", _run(["run", "midi-transcribe", "--input", str(_corrupt(out)), "--out", str(out / "corrupt.json")])),
        "silence": _require_failed(out / "silence.json", _run(["run", "midi-transcribe", "--input", str(_full_silence(out)), "--out", str(out / "silence.json")])),
    }
    report = {
        "sha": os.environ.get("GITHUB_SHA"),
        "cause": (
            "No caso B o onset do modelo em MIDI 88 fica acima de 0,5 com o melodia_trick "
            "ligado ou desligado. O contorno dessa oitava é 0,327, contra 0,333 da nota fraca "
            "de uma díade válida. Não há limiar que apague só a oitava espúria."
        ),
        "tolerances": {"pitch_semitones": 1, "onset_s": 0.08, "offset_s": 0.08},
        "cases": cases,
        "F": {name: {"status": "PASS", "receipt": receipt["status"]} for name, receipt in negatives.items()},
        "not_corrected": ["B", "D"],
    }
    (out / "midi-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    lines = ["## MIDI A–F", ""]
    for case in cases:
        lines.append(f"- {case['id']} {case['title']}: {case['status']}")
    lines.append("- F ausente/corrompido/silêncio: PASS (sem recibo success)")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    print("midi matrix", json.dumps({case["id"]: case["status"] for case in cases} | {"F": "PASS"}, ensure_ascii=False))
    for case in cases:
        if case["status"] == "FAIL":
            print(f"::warning title=MIDI caso {case['id']}::FAIL reproduzido, sem correção segura")


def _corrupt(out: Path) -> Path:
    path = out / "corrupt.wav"
    path.write_bytes(b"not a wav")
    return path


def _full_silence(out: Path) -> Path:
    path = out / "silence.wav"
    _silence(path)
    return path


if __name__ == "__main__":
    try:
        main()
    except MidiError as exc:
        raise SystemExit(str(exc)) from exc

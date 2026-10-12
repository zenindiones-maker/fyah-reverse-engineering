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


def _run(args: list[str], extra_env: dict | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-m", "tools", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
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
    midi = out / f"{spec['id']}.mid"
    log_path = out / f"{spec['id']}.log"
    receipt_path = out / f"{spec['id']}.json.receipt.json"
    for stale in (output, midi, log_path, receipt_path):
        stale.unlink(missing_ok=True)
    result = _run(["run", "midi-transcribe", "--input", str(wav), "--out", str(output)])
    log_path.write_text(result.stdout + "\n" + result.stderr)

    if spec["expect"] == "BLOCKED":
        if result.returncode == 0 or output.exists() or midi.exists():
            raise SystemExit(
                f"caso {spec['id']} deveria bloquear sem publicar MIDI/JSON; "
                f"returncode={result.returncode}, output={output.exists()}, midi={midi.exists()}\n{result.stderr}"
            )
        if not receipt_path.is_file():
            raise SystemExit(f"caso {spec['id']} não produziu recibo de bloqueio")
        receipt = json.loads(receipt_path.read_text())
        if receipt["status"] != "blocked" or receipt["output_artifacts"] or receipt["provenance"].get("policy") != "harmonic_ambiguity":
            raise SystemExit(f"caso {spec['id']} não ficou blocked por política: {receipt}")
        message = log_path.read_text()
        if "ambiguidade harmônica" not in message.lower() or f"MIDI {spec['blocked_pitch']}" not in message:
            raise SystemExit(f"caso {spec['id']} não nomeou MIDI {spec['blocked_pitch']}: {message}")
        raw = _raw_override(out, spec, wav)
        return {
            "id": spec["id"],
            "title": spec["title"],
            "status": "BLOCKED",
            "expected_status": "BLOCKED",
            "musical_correction": "PENDENTE",
            "reason": "ambiguidade harmônica; saída MIDI recusada por segurança",
            "midi_published": False,
            "receipt_status": receipt["status"],
            "receipt_exit_code": receipt["exit_code"],
            "receipt_output_artifacts": receipt["output_artifacts"],
            "log": log_path.name,
            "raw_override": raw,
        }

    if result.returncode != 0:
        raise SystemExit(f"caso {spec['id']} não transcreveu: {result.returncode}\n{result.stderr}")
    payload = json.loads(output.read_text())
    detected = parse_midi_notes(midi)
    score = evaluate_notes(detected, spec["notes"], spec["partials"])
    receipt = json.loads(receipt_path.read_text())
    artifacts = {item["path"]: item["sha256"] for item in receipt["output_artifacts"]}
    for name in (output.name, midi.name):
        if artifacts.get(name) != _sha256(out / name):
            raise SystemExit(f"SHA-256 divergente em {name}")
    if receipt["status"] != "success" or payload["model"]["sha256"] != PINNED_MODEL_SHA256:
        raise SystemExit(f"caso {spec['id']} sem recibo ou modelo fixado")
    if payload.get("harmonic_ambiguities") or payload.get("harmonic_ambiguity_override"):
        raise SystemExit(f"caso {spec['id']} publicou ambiguidade como sucesso: {payload.get('harmonic_ambiguities')}")
    if score["status"] != spec["expect"]:
        raise SystemExit(f"caso {spec['id']} classificou {score['status']}, referência prévia era {spec['expect']}: {score}")
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


def _raw_override(out: Path, spec: dict, wav: Path) -> dict:
    """Explicit raw model output. This is evidence, not a musical PASS."""
    output = out / f"{spec['id']}-raw.json"
    midi = out / f"{spec['id']}-raw.mid"
    for stale in (output, midi, out / f"{spec['id']}-raw.json.receipt.json"):
        stale.unlink(missing_ok=True)
    result = _run(
        ["run", "midi-transcribe", "--input", str(wav), "--out", str(output)],
        {"FYAH_MIDI_ALLOW_HARMONIC_AMBIGUITY": "1"},
    )
    (out / f"{spec['id']}-raw.log").write_text(result.stdout + "\n" + result.stderr)
    if result.returncode != 0 or not midi.is_file():
        raise SystemExit(f"override do caso {spec['id']} não preservou a saída bruta: {result.stderr}")
    payload = json.loads(output.read_text())
    detected = parse_midi_notes(midi)
    pitches = {note["pitch"] for note in detected}
    if spec["blocked_pitch"] not in pitches:
        raise SystemExit(f"override do caso {spec['id']} não contém MIDI {spec['blocked_pitch']}: {sorted(pitches)}")
    if payload.get("harmonic_ambiguity_override") is not True or not payload.get("harmonic_ambiguities"):
        raise SystemExit(f"override do caso {spec['id']} não ficou rastreável no JSON")
    receipt = json.loads((out / f"{spec['id']}-raw.json.receipt.json").read_text())
    if receipt["status"] != "success" or receipt["provenance"].get("harmonic_ambiguity_override") is not True:
        raise SystemExit(f"override do caso {spec['id']} não ficou rastreável no recibo: {receipt['provenance']}")
    artifacts = {item["path"]: item["sha256"] for item in receipt["output_artifacts"]}
    for name in (output.name, midi.name):
        if artifacts.get(name) != _sha256(out / name):
            raise SystemExit(f"SHA-256 divergente no override {name}")
    return {
        "musical_status": "PENDENTE",
        "detected": [
            {"pitch": note["pitch"], "start_s": round(note["start_s"], 6), "end_s": round(note["end_s"], 6)}
            for note in detected
        ],
        "ambiguities": payload["harmonic_ambiguities"],
        "receipt_sha256": artifacts,
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
    cases = [_positive(out, specs[name]) for name in ("A", "B", "C", "D", "E", "O")]
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
        "not_transcribed": ["B", "D", "O"],
        "musical_correction": "PENDENTE",
        "policy": "ambiguidade harmônica bloqueia antes do MIDI; o override explicito preserva a saída bruta e não é um PASS musical",
    }
    (out / "midi-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    lines = ["## MIDI A–F", ""]
    for case in cases:
        lines.append(f"- {case['id']} {case['title']}: {case['status']}")
    lines.append("- B/D/O: BLOCKED. A correção musical da oitava continua pendente.")
    lines.append("- F ausente/corrompido/silêncio: PASS (sem recibo success)")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    print("midi matrix", json.dumps({case["id"]: case["status"] for case in cases} | {"F": "PASS"}, ensure_ascii=False))
    for case in cases:
        if case["status"] == "BLOCKED":
            print(f"::warning title=MIDI caso {case['id']}::BLOCKED por ambiguidade; correção musical pendente")


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

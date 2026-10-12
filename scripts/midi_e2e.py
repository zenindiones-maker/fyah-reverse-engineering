"""Matriz MIDI pelo dispatcher.

A, C e E são PASS musical. B, D e O ficam BLOCKED. F1 é BLOCKED porque a
entrada não existe. F2 e F3 são FAIL. Nenhum desses estados é reescrito
como sucesso, e o override bruto não entra na lista de PASS.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from audio.midi_transcribe import (
    HARMONIC_BLOCK_EXIT,
    PINNED_MODEL_SHA256,
    PINNED_VERSION,
    MidiError,
    case_specs,
    evaluate_notes,
    parse_midi_notes,
    render_wav,
    verify_model,
)

NEGATIVE_CONTRACT = {
    "F1": {
        "title": "arquivo ausente",
        "status": "BLOCKED",
        "receipt_status": "blocked",
        "exit_code": 2,
        "error_category": "input_or_policy_rejection",
    },
    "F2": {
        "title": "WAV corrompido",
        "status": "FAIL",
        "receipt_status": "failed",
        "exit_code": 1,
        "error_category": "CalledProcessError",
    },
    "F3": {
        "title": "silêncio total",
        "status": "FAIL",
        "receipt_status": "failed",
        "exit_code": 1,
        "error_category": "CalledProcessError",
    },
}
EXPECTED_GROUPS = {
    "PASS": ["A", "C", "E"],
    "BLOCKED": ["B", "D", "O", "F1"],
    "FAIL": ["F2", "F3"],
}
ALLOWED_MIDI = {"A.mid", "C.mid", "E.mid", "B-raw.mid", "D-raw.mid", "O-raw.mid", "O-h-raw.mid"}
HARNESS_VERSION = "2"


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


def observed_status(receipt: dict) -> str:
    """Map the receipt. A failed receipt is FAIL, never BLOCKED."""
    status = receipt.get("status")
    if status == "blocked":
        return "BLOCKED"
    if status == "failed":
        return "FAIL"
    if status == "success":
        return "PASS"
    raise SystemExit(f"recibo sem estado conhecido: {status}")


def assert_report_matches_receipt(case: dict) -> None:
    """Fail if the report label is not the receipt label."""
    reported = case.get("status")
    receipt_status = case.get("receipt_status")
    expected = {"BLOCKED": "blocked", "FAIL": "failed", "PASS": "success"}.get(reported)
    if expected is None or receipt_status != expected:
        raise SystemExit(
            f"{case.get('id')} relatório {reported} discorda do recibo {receipt_status}"
        )


def observe_negative(case_id: str, receipt: dict, returncode: int, output: Path) -> dict:
    """Record F1–F3 as BLOCKED or FAIL. Never relabel those receipts as PASS."""
    expected = NEGATIVE_CONTRACT[case_id]
    midi = output.with_suffix(".mid")
    problems = []
    observed = observed_status(receipt)
    if expected["status"] not in ("BLOCKED", "FAIL"):
        problems.append("contrato negativo não pode exigir PASS")
    if observed != expected["status"]:
        problems.append(f"recibo {receipt.get('status')} não é {expected['status']}")
    if returncode != expected["exit_code"]:
        problems.append(f"processo exit {returncode}")
    if receipt.get("status") != expected["receipt_status"]:
        problems.append(f"recibo {receipt.get('status')}")
    if receipt.get("exit_code") != expected["exit_code"]:
        problems.append(f"recibo exit {receipt.get('exit_code')}")
    if receipt.get("error_category") != expected["error_category"]:
        problems.append(f"categoria {receipt.get('error_category')}")
    if receipt.get("output_artifacts"):
        problems.append("artefatos publicados")
    if receipt.get("status") == "success":
        problems.append("recibo success")
    if output.exists() or midi.exists():
        problems.append("JSON ou MIDI publicado")
    if problems:
        raise SystemExit(f"{case_id} fora do contrato: {problems}")
    receipt_path = output.parent / (output.name + ".receipt.json")
    return {
        "id": case_id,
        "title": expected["title"],
        "status": observed,
        "counts_as_success": False,
        "midi_published": False,
        "process_exit_code": returncode,
        "receipt_status": receipt["status"],
        "receipt_exit_code": receipt["exit_code"],
        "receipt_error_category": receipt["error_category"],
        "receipt_run_id": receipt.get("run_id"),
        "receipt_started_at": receipt.get("started_at"),
        "receipt_output_artifacts": [],
        "receipt_sha256": _sha256(receipt_path) if receipt_path.is_file() else None,
    }


def group_statuses(cases: list[dict]) -> dict[str, list[str]]:
    """Split ids into PASS, BLOCKED and FAIL. A block or a failure is not a success."""
    groups = {"PASS": [], "BLOCKED": [], "FAIL": []}
    for case in cases:
        status = case.get("status")
        if status not in groups:
            raise SystemExit(f"estado fora de PASS, BLOCKED ou FAIL: {case.get('id')}={status}")
        if status != "PASS" and case.get("counts_as_success") is not False:
            raise SystemExit(f"{case.get('id')} converte {status} em sucesso")
        if status == "PASS" and case.get("counts_as_success") is False:
            raise SystemExit(f"{case.get('id')} é PASS e ao mesmo tempo não-sucesso")
        groups[status].append(case["id"])
    return groups


def _fresh_out() -> Path:
    """Drop the workspace output so the uploaded artifact cannot contain an older run."""
    out = ROOT / "out"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    return out


def _execution_stamp() -> dict:
    return {
        "github_sha": os.environ.get("GITHUB_SHA"),
        "head_sha": os.environ.get("FYAH_MIDI_HEAD_SHA") or os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
    }


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
        if result.returncode != HARMONIC_BLOCK_EXIT or output.exists() or midi.exists():
            raise SystemExit(
                f"caso {spec['id']} deveria bloquear sem publicar MIDI/JSON; "
                f"returncode={result.returncode}, output={output.exists()}, midi={midi.exists()}\n{result.stderr}"
            )
        if not receipt_path.is_file():
            raise SystemExit(f"caso {spec['id']} não produziu recibo de bloqueio")
        receipt = json.loads(receipt_path.read_text())
        if (
            receipt["status"] != "blocked"
            or receipt.get("exit_code") != HARMONIC_BLOCK_EXIT
            or receipt["output_artifacts"]
            or receipt["provenance"].get("policy") != "harmonic_ambiguity"
        ):
            raise SystemExit(f"caso {spec['id']} não ficou blocked por política: {receipt}")
        observed = observed_status(receipt)
        if observed != "BLOCKED":
            raise SystemExit(f"caso {spec['id']} recibo {receipt['status']} não é bloqueio")
        message = log_path.read_text()
        if "ambiguidade harmônica" not in message.lower() or f"MIDI {spec['blocked_pitch']}" not in message:
            raise SystemExit(f"caso {spec['id']} não nomeou MIDI {spec['blocked_pitch']}: {message}")
        raw = _raw_override(out, spec, wav)
        return {
            "id": spec["id"],
            "title": spec["title"],
            "status": observed,
            "expected_status": "BLOCKED",
            "counts_as_success": False,
            "musical_correction": "PENDENTE",
            "reason": "ambiguidade harmônica; saída MIDI recusada por segurança",
            "midi_published": False,
            "process_exit_code": result.returncode,
            "receipt_status": receipt["status"],
            "receipt_exit_code": receipt["exit_code"],
            "receipt_error_category": receipt.get("error_category"),
            "receipt_run_id": receipt.get("run_id"),
            "receipt_started_at": receipt.get("started_at"),
            "receipt_sha256": _sha256(receipt_path),
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
    observed = observed_status(receipt)
    if observed != "PASS" or score["status"] != "PASS":
        raise SystemExit(f"caso {spec['id']} recibo {receipt['status']} não sustenta PASS musical")
    return {
        "id": spec["id"],
        "title": spec["title"],
        "status": observed,
        "expected_status": spec["expect"],
        "counts_as_success": True,
        "receipt_status": receipt["status"],
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
        "receipt_run_id": receipt.get("run_id"),
        "receipt_started_at": receipt.get("started_at"),
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
    missing = [pitch for pitch in spec.get("preserved_pitches", ()) if pitch not in pitches]
    if missing:
        raise SystemExit(f"override do caso {spec['id']} apagou notas {missing}; detectadas {sorted(pitches)}")
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
        "counts_as_success": False,
        "receipt_status": receipt["status"],
        "receipt_run_id": receipt.get("run_id"),
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


def _octave_harmonic_spec() -> dict:
    """Same pitches as a played octave, generated as one tone plus its second partial."""
    return {
        "id": "O-h",
        "title": "fundamental mais parcial h2",
        "expect": "BLOCKED",
        "blocked_pitch": 81,
        "preserved_pitches": (69, 81),
        "tail_s": 0.50,
        "notes": [{
            "name": "A4",
            "frequency_hz": 440.0,
            "pitch": 69,
            "start_s": 0.40,
            "duration_s": 0.80,
            "partials": ((440.0, 1.0), (880.0, 0.8)),
        }],
        "partials": (),
    }


def _negative(out: Path, case_id: str, source: Path) -> dict:
    output = out / f"{case_id}.json"
    for stale in (output, output.with_suffix(".mid"), out / f"{case_id}.json.receipt.json"):
        stale.unlink(missing_ok=True)
    result = _run(["run", "midi-transcribe", "--input", str(source), "--out", str(output)])
    (out / f"{case_id}.log").write_text(result.stdout + "\n" + result.stderr)
    receipt_path = out / f"{case_id}.json.receipt.json"
    if not receipt_path.is_file():
        raise SystemExit(f"{case_id} não gravou recibo nesta execução")
    receipt = json.loads(receipt_path.read_text())
    return observe_negative(case_id, receipt, result.returncode, output)


def main() -> None:
    out = _fresh_out()
    _reject_corrupt_model()
    specs = case_specs()
    cases = [_positive(out, specs[name]) for name in ("A", "B", "C", "D", "E", "O")]
    cases.extend([
        _negative(out, "F1", out / "nao-existe.wav"),
        _negative(out, "F2", _corrupt(out)),
        _negative(out, "F3", _full_silence(out)),
    ])
    harmonic = _positive(out, _octave_harmonic_spec())
    played = next(case for case in cases if case["id"] == "O")
    played["conditions"] = [
        {
            "id": "O",
            "kind": "intentional_octave",
            "status": played["status"],
            "receipt_status": played["receipt_status"],
            "kept_pitches": [note["pitch"] for note in played["raw_override"]["detected"]],
        },
        {
            "id": "O-h",
            "kind": "fundamental_plus_partial",
            "status": harmonic["status"],
            "receipt_status": harmonic["receipt_status"],
            "kept_pitches": [note["pitch"] for note in harmonic["raw_override"]["detected"]],
        },
    ]
    played["distinguished"] = False
    played["harmonic_twin"] = harmonic
    if harmonic["status"] != "BLOCKED" or played["status"] != "BLOCKED":
        raise SystemExit("O e O-h não estão ambos bloqueados; a oitava não foi distinguida nem corrigida")
    for case in (*cases, harmonic):
        assert_report_matches_receipt(case)
    groups = group_statuses(cases)
    if groups != EXPECTED_GROUPS:
        raise SystemExit(f"grupos divergentes do contrato: {groups}")
    published = {path.name for path in out.glob("*.mid")}
    if published != ALLOWED_MIDI:
        raise SystemExit(f"MIDI fora da execução atual: {sorted(published)}")
    for case in cases:
        if case["status"] != "PASS" and (out / f"{case['id']}.mid").exists():
            raise SystemExit(f"{case['id']} publicou MIDI sem ser PASS")
        raw = case.get("raw_override")
        if raw and raw.get("musical_status") != "PENDENTE":
            raise SystemExit(f"{case['id']} trata o override como PASS musical")
        if raw and raw.get("counts_as_success") is not False:
            raise SystemExit(f"{case['id']} conta o override como sucesso")
    if (out / "O-h.mid").exists():
        raise SystemExit("O-h publicou MIDI sem ser PASS")
    stamp = _execution_stamp()
    if os.environ.get("GITHUB_ACTIONS") == "true":
        if stamp.get("run_id") != os.environ.get("GITHUB_RUN_ID") or not stamp.get("head_sha"):
            raise SystemExit(f"artefato sem identidade da execução atual: {stamp}")
        if stamp["head_sha"] != os.environ.get("FYAH_MIDI_HEAD_SHA"):
            raise SystemExit("SHA do relatório não é o commit testado")
    report = {
        "execution": stamp,
        "harness": {"name": "scripts/midi_e2e.py", "version": HARNESS_VERSION},
        "model": {"name": "basic-pitch", "version": PINNED_VERSION, "sha256": PINNED_MODEL_SHA256},
        "cause": (
            "No caso B o onset do modelo em MIDI 88 fica acima de 0,5 com o melodia_trick "
            "ligado ou desligado. O contorno dessa oitava é 0,327, contra 0,333 da nota fraca "
            "de uma díade válida. Não há limiar que apague só a oitava espúria."
        ),
        "tolerances": {"pitch_semitones": 1, "onset_s": 0.08, "offset_s": 0.08},
        "classification": groups,
        "cases": cases,
        "not_transcribed": ["B", "D", "O"],
        "musical_correction": "PENDENTE",
        "policy": (
            "PASS, BLOCKED e FAIL ficam em listas separadas. "
            "Bloqueio e falha não são sucesso. A correção musical da oitava continua pendente."
        ),
    }
    (out / "midi-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    lines = [
        "## MIDI — contrato desta execução",
        "",
        f"- PASS: {', '.join(groups['PASS'])}",
        f"- BLOCKED: {', '.join(groups['BLOCKED'])}",
        f"- FAIL: {', '.join(groups['FAIL'])}",
        "- B/D/O continuam BLOCKED. Isso não é correção musical.",
        "- F1 BLOCKED (ausente). F2 FAIL (corrompido). F3 FAIL (silêncio). Sem MIDI.",
        f"- run: {report['execution']['run_id']} sha: {report['execution']['github_sha']}",
    ]
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    print("midi matrix", json.dumps(groups, ensure_ascii=False))
    for case in cases:
        if case["status"] == "BLOCKED":
            print(f"::warning title=MIDI caso {case['id']}::BLOCKED; não é sucesso")
        elif case["status"] == "FAIL":
            print(f"::warning title=MIDI caso {case['id']}::FAIL; não é sucesso")


def _corrupt(out: Path) -> Path:
    path = out / "F2.wav"
    path.write_bytes(b"not a wav")
    return path


def _full_silence(out: Path) -> Path:
    path = out / "F3.wav"
    _silence(path)
    return path


if __name__ == "__main__":
    try:
        main()
    except MidiError as exc:
        raise SystemExit(str(exc)) from exc

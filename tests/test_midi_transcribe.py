import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from audio.midi_transcribe import MidiError, match_reference, parse_midi_notes, verify_model, write_reference_wav


def _write_midi(path: Path, notes: list[tuple[int, float, float]]) -> None:
    division = 220
    microseconds = 500000

    def ticks(second: float) -> int:
        return int(round(second * division * 1_000_000 / microseconds))

    events = []
    for pitch, start, end in notes:
        events.append((ticks(start), 0x90, pitch, 80))
        events.append((ticks(end), 0x80, pitch, 0))
    events.sort()
    track = bytearray()
    last = 0
    for tick, status, pitch, velocity in events:
        delta = tick - last
        last = tick
        encoded = [delta & 0x7F]
        delta >>= 7
        while delta:
            encoded.append((delta & 0x7F) | 0x80)
            delta >>= 7
        track.extend(reversed(encoded))
        track.extend((status, pitch, velocity))
    track.extend(b"\x00\xff\x2f\x00")
    tempo = bytearray(b"\x00\xff\x51\x03\x07\xa1\x20\x00\xff\x2f\x00")
    data = bytearray(b"MThd\x00\x00\x00\x06\x00\x01\x00\x02\x00\xdc")
    for payload in (tempo, track):
        data.extend(b"MTrk")
        data.extend(len(payload).to_bytes(4, "big"))
        data.extend(payload)
    path.write_bytes(data)


def test_parser_and_reference_tolerances(tmp_path):
    midi = tmp_path / "ok.mid"
    _write_midi(midi, [(69, 0.4068, 0.9523), (72, 1.4045, 1.9614), (76, 2.4045, 2.9500)])
    pairs = match_reference(parse_midi_notes(midi))
    assert [item["name"] for item in pairs] == ["A4", "C5", "E5"]
    assert all(abs(item["onset_error_s"]) <= 0.08 for item in pairs)
    shifted = tmp_path / "late.mid"
    _write_midi(shifted, [(69, 0.70, 0.95), (72, 1.40, 1.95), (76, 2.40, 2.95)])
    with pytest.raises(MidiError, match="A4"):
        match_reference(parse_midi_notes(shifted))
    extra = tmp_path / "extra.mid"
    _write_midi(extra, [(69, 0.40, 0.95), (60, 1.05, 1.20), (72, 1.40, 1.95), (76, 2.40, 2.95)])
    with pytest.raises(MidiError, match="não previstas"):
        match_reference(parse_midi_notes(extra))


def test_model_hash_is_rejected_when_bytes_change(tmp_path):
    model = tmp_path / "nmp.onnx"
    model.write_bytes(b"not the pinned model")
    with pytest.raises(MidiError, match="hash"):
        verify_model(model, "0.4.0")
    with pytest.raises(MidiError, match="versão"):
        verify_model(model, "0.0.0")


def test_invalid_inputs_do_not_publish_a_successful_midi(tmp_path, monkeypatch):
    monkeypatch.setenv("FYAH_RE_VENVS", str(tmp_path / "absent-venvs"))
    env = os.environ.copy()
    env["FYAH_RE_VENVS"] = str(tmp_path / "absent-venvs")
    root = Path(__file__).resolve().parents[1]

    def run(source: Path, out: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "tools", "run", "midi-transcribe", "--input", str(source), "--out", str(out)],
            cwd=root, capture_output=True, text=True, env=env,
        )

    missing = run(tmp_path / "nope.wav", tmp_path / "missing.json")
    assert missing.returncode != 0
    assert not (tmp_path / "missing.json").exists()
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    empty_run = run(empty, tmp_path / "empty.json")
    assert empty_run.returncode != 0
    assert not (tmp_path / "empty.mid").exists()
    tone = tmp_path / "tone.wav"
    write_reference_wav(tone)
    blocked = run(tone, tmp_path / "blocked.json")
    assert blocked.returncode != 0
    assert not (tmp_path / "blocked.json").exists()
    assert not (tmp_path / "blocked.mid").exists()
    receipt = json.loads((tmp_path / "blocked.json.receipt.json").read_text())
    assert receipt["status"] != "success"
    assert receipt["output_artifacts"] == []
    corrupt = tmp_path / "corrupt.wav"
    with wave.open(str(tone), "rb"):
        pass
    corrupt.write_bytes(b"not a wav")
    corrupt_run = run(corrupt, tmp_path / "corrupt.json")
    assert corrupt_run.returncode != 0
    assert not (tmp_path / "corrupt.mid").exists()


def test_harmonic_octave_stays_a_failure_under_the_same_tolerances():
    from audio.midi_transcribe import case_specs, evaluate_notes

    spec = case_specs()["B"]
    detected = [
        {"pitch": 69, "start_s": 0.406, "end_s": 0.987},
        {"pitch": 72, "start_s": 1.405, "end_s": 1.987},
        {"pitch": 76, "start_s": 2.405, "end_s": 2.973},
        {"pitch": 88, "start_s": 2.393, "end_s": 2.892},
    ]
    score = evaluate_notes(detected, spec["notes"], spec["partials"])
    assert score["status"] == "FAIL"
    assert score["missing"] == []
    assert [item["pitch"] for item in score["harmonic_confusions"]] == [88]
    assert score["unrelated_extras"] == []
    assert abs(score["matched"][2]["onset_error_s"]) <= 0.08
    assert score["matched"][2]["pitch"] == 76



def test_harmonic_candidates_are_ambiguous_not_silently_deleted():
    from audio.midi_transcribe import harmonic_ambiguities

    harmonic_series = [
        {"pitch": 69, "start_s": 0.40, "end_s": 1.60},
        {"pitch": 97, "start_s": 0.405, "end_s": 1.55},
    ]
    candidates = harmonic_ambiguities(harmonic_series)
    assert candidates == [{"lower_pitch": 69, "upper_pitch": 97, "harmonic_number": 5}]

    # Uma oitava realmente tocada com onset/duração alinhados é acusticamente
    # ambígua sob este critério; não pode ser removida silenciosamente.
    played_octave = [
        {"pitch": 69, "start_s": 0.40, "end_s": 1.20},
        {"pitch": 81, "start_s": 0.40, "end_s": 1.20},
    ]
    assert harmonic_ambiguities(played_octave) == [
        {"lower_pitch": 69, "upper_pitch": 81, "harmonic_number": 2}
    ]
    assert harmonic_ambiguities([
        {"pitch": 69, "start_s": 0.40, "end_s": 1.20},
        {"pitch": 76, "start_s": 0.40, "end_s": 1.20},
    ]) == []
    assert harmonic_ambiguities([
        {"pitch": 69, "start_s": 0.40, "end_s": 1.20},
        {"pitch": 82, "start_s": 0.40, "end_s": 1.20},
    ]) == []


def test_negative_contract_keeps_block_and_fail_out_of_pass(tmp_path):
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "scripts" / "midi_e2e.py"
    spec = importlib.util.spec_from_file_location("midi_e2e_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert {item["status"] for item in module.NEGATIVE_CONTRACT.values()} == {"BLOCKED", "FAIL"}
    blocked = {
        "status": "blocked",
        "exit_code": 2,
        "error_category": "input_or_policy_rejection",
        "output_artifacts": [],
        "run_id": "f1-run",
        "started_at": "2026-10-12T22:30:00Z",
    }
    failed = {
        "status": "failed",
        "exit_code": 1,
        "error_category": "CalledProcessError",
        "output_artifacts": [],
        "run_id": "f-run",
        "started_at": "2026-10-12T22:30:01Z",
    }
    f1 = module.observe_negative("F1", blocked, 2, tmp_path / "F1.json")
    f2 = module.observe_negative("F2", failed, 1, tmp_path / "F2.json")
    f3 = module.observe_negative("F3", dict(failed, run_id="f3-run"), 1, tmp_path / "F3.json")
    assert [f1["status"], f2["status"], f3["status"]] == ["BLOCKED", "FAIL", "FAIL"]
    assert all(item["counts_as_success"] is False for item in (f1, f2, f3))
    groups = module.group_statuses([
        {"id": "A", "status": "PASS", "counts_as_success": True},
        {"id": "C", "status": "PASS", "counts_as_success": True},
        {"id": "E", "status": "PASS", "counts_as_success": True},
        {"id": "B", "status": "BLOCKED", "counts_as_success": False},
        {"id": "D", "status": "BLOCKED", "counts_as_success": False},
        {"id": "O", "status": "BLOCKED", "counts_as_success": False},
        f1, f2, f3,
    ])
    assert groups == module.EXPECTED_GROUPS
    with pytest.raises(SystemExit, match="recibo success"):
        module.observe_negative("F1", {**blocked, "status": "success", "exit_code": 0}, 0, tmp_path / "F1.json")
    with pytest.raises(SystemExit, match="converte BLOCKED"):
        module.group_statuses([{"id": "B", "status": "BLOCKED", "counts_as_success": True}])
    assert module.observed_status({"status": "failed"}) == "FAIL"
    assert module.observed_status({"status": "blocked"}) == "BLOCKED"
    with pytest.raises(SystemExit, match="discorda do recibo"):
        module.assert_report_matches_receipt({"id": "B", "status": "BLOCKED", "receipt_status": "failed"})

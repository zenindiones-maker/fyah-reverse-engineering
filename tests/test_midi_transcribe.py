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

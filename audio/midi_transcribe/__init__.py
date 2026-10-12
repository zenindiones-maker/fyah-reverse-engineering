"""Transcrição local áudio→MIDI com basic-pitch ONNX. Sem API e sem GPU."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import struct
import subprocess
import wave
from pathlib import Path

PINNED_VERSION = "0.4.0"
PINNED_MODEL_SHA256 = "2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec"
MODEL_RELATIVE = Path("saved_models") / "icassp_2022" / "nmp.onnx"
MODEL_ORIGIN = "PyPI basic-pitch==0.4.0 basic_pitch/saved_models/icassp_2022/nmp.onnx"
LICENSE = "Apache-2.0"
SAMPLE_RATE = 22050
# Defaults da biblioteca, os mesmos usados na prova. Não foram relaxados para forçar o teste.
PARAMETERS = {
    "onset_threshold": 0.5,
    "frame_threshold": 0.3,
    "minimum_note_length": 127.7,
    "minimum_frequency": None,
    "maximum_frequency": None,
    "multiple_pitch_bends": False,
    "melodia_trick": True,
    "midi_tempo": 120.0,
}
PITCH_TOLERANCE_SEMITONES = 1
ONSET_TOLERANCE_S = 0.08
OFFSET_TOLERANCE_S = 0.08
REFERENCE_NOTES = (
    {"name": "A4", "frequency_hz": 440.0, "pitch": 69, "start_s": 0.40, "duration_s": 0.55},
    {"name": "C5", "frequency_hz": 523.25, "pitch": 72, "start_s": 1.40, "duration_s": 0.55},
    {"name": "E5", "frequency_hz": 659.25, "pitch": 76, "start_s": 2.40, "duration_s": 0.55},
)
REFERENCE_TAIL_S = 0.50
LIMITATIONS = [
    "provado só com três senoides isoladas (A4, C5, E5); não é transcrição de música completa",
    "polifonia, instrumentos reais, notas sobrepostas e pitch bend não foram testados",
    "o modelo emite um frame a cada ~11,6 ms; o teste aceita ±1 semitom e ±80 ms no início e no fim",
    "uma série harmônica no mesmo teste gerou uma oitava extra e foi rejeitada; o sinal da prova é seno puro",
]


class MidiError(RuntimeError):
    """Transcription did not produce a trustworthy MIDI file."""


def write_reference_wav(path: str | Path) -> None:
    """Deterministic isolated sines. Harmonics made the model invent an octave."""
    destination = Path(path)
    total = max(note["start_s"] + note["duration_s"] for note in REFERENCE_NOTES) + REFERENCE_TAIL_S
    frames = [0.0] * int(SAMPLE_RATE * total)
    for note in REFERENCE_NOTES:
        start = int(note["start_s"] * SAMPLE_RATE)
        length = int(note["duration_s"] * SAMPLE_RATE)
        for index in range(length):
            t = index / SAMPLE_RATE
            envelope = min(1.0, t / 0.02) * min(1.0, (note["duration_s"] - t) / 0.04)
            frames[start + index] = 0.8 * envelope * math.sin(2 * math.pi * note["frequency_hz"] * t)
    raw = bytearray()
    for sample in frames:
        value = int(max(-1.0, min(1.0, sample)) * 32767)
        raw.extend(value.to_bytes(2, "little", signed=True))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(raw)


def verify_model(model_path: Path, package_version: str) -> str:
    if package_version != PINNED_VERSION:
        raise MidiError(f"versão de basic-pitch divergente: {package_version}; exigida {PINNED_VERSION}")
    if not model_path.is_file():
        raise MidiError("modelo ONNX ausente")
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if digest != PINNED_MODEL_SHA256:
        raise MidiError(f"hash do modelo divergente: {digest}")
    return digest


def _venv_python() -> Path | None:
    root = os.environ.get("FYAH_RE_VENVS", "")
    if not root:
        return None
    candidate = Path(root) / "basicpitch" / "bin" / "python"
    return candidate if candidate.is_file() else None


def _read_vlq(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[pos]
        pos += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, pos


def parse_midi_notes(path: str | Path) -> list[dict]:
    """Read note-on/off pairs as seconds using the file tempo map. No third-party parser."""
    data = Path(path).read_bytes()
    if len(data) < 14 or data[:4] != b"MThd":
        raise MidiError("arquivo MIDI inválido")
    header_len = int.from_bytes(data[4:8], "big")
    _fmt, ntrks, division = struct.unpack(">HHH", data[8:14])
    if division & 0x8000:
        raise MidiError("divisão SMPTE não suportada")
    pos = 8 + header_len
    tracks = []
    for _ in range(ntrks):
        if data[pos:pos + 4] != b"MTrk":
            raise MidiError("trilha MIDI inválida")
        length = int.from_bytes(data[pos + 4:pos + 8], "big")
        pos += 8
        end = pos + length
        events = []
        tick = 0
        status = None
        while pos < end:
            delta, pos = _read_vlq(data, pos)
            tick += delta
            if data[pos] & 0x80:
                status = data[pos]
                pos += 1
            if status is None:
                raise MidiError("evento MIDI sem status")
            if status == 0xFF:
                meta = data[pos]
                pos += 1
                size, pos = _read_vlq(data, pos)
                payload = data[pos:pos + size]
                pos += size
                events.append((tick, "meta", meta, payload))
                if meta == 0x2F:
                    break
            elif status in (0xF0, 0xF7):
                size, pos = _read_vlq(data, pos)
                pos += size
            else:
                kind = status & 0xF0
                needed = 2 if kind in (0x80, 0x90, 0xA0, 0xB0, 0xE0) else 1
                payload = data[pos:pos + needed]
                pos += needed
                events.append((tick, "midi", kind, payload))
        pos = end
        tracks.append(events)
    tempos = [(0, 500000)]
    for events in tracks:
        for tick, kind, meta, payload in (event for event in events if event[1] == "meta"):
            if meta == 0x51 and len(payload) == 3:
                tempos.append((tick, int.from_bytes(payload, "big")))
    tempos.sort()

    def seconds(tick: int) -> float:
        last_tick = 0
        microseconds = 500000
        elapsed = 0.0
        for change_tick, change in tempos:
            if change_tick >= tick:
                break
            elapsed += (change_tick - last_tick) * microseconds / division / 1_000_000
            last_tick, microseconds = change_tick, change
        elapsed += (tick - last_tick) * microseconds / division / 1_000_000
        return elapsed

    open_notes: dict[int, list[tuple[float, int]]] = {}
    notes = []
    for events in tracks:
        for tick, kind, status_kind, payload in (event for event in events if event[1] == "midi"):
            if status_kind not in (0x80, 0x90):
                continue
            pitch = payload[0]
            velocity = payload[1]
            when = seconds(tick)
            if status_kind == 0x90 and velocity > 0:
                open_notes.setdefault(pitch, []).append((when, velocity))
            elif open_notes.get(pitch):
                start, vel = open_notes[pitch].pop(0)
                notes.append({"pitch": pitch, "start_s": start, "end_s": when, "velocity": vel})
    notes.sort(key=lambda note: (note["start_s"], note["pitch"]))
    return notes


def match_reference(detected: list[dict]) -> list[dict]:
    """Pair every reference note and reject any extra note, including notes in the gaps."""
    used: set[int] = set()
    pairs = []
    for reference in REFERENCE_NOTES:
        expected_end = reference["start_s"] + reference["duration_s"]
        found = None
        for index, note in enumerate(detected):
            if index in used:
                continue
            if abs(note["pitch"] - reference["pitch"]) > PITCH_TOLERANCE_SEMITONES:
                continue
            if abs(note["start_s"] - reference["start_s"]) > ONSET_TOLERANCE_S:
                continue
            if abs(note["end_s"] - expected_end) > OFFSET_TOLERANCE_S:
                continue
            found = index
            break
        if found is None:
            raise MidiError(f"nota de referência sem correspondência: {reference['name']}")
        used.add(found)
        note = detected[found]
        pairs.append({
            "name": reference["name"],
            "pitch": note["pitch"],
            "expected_pitch": reference["pitch"],
            "onset_error_s": round(note["start_s"] - reference["start_s"], 6),
            "offset_error_s": round(note["end_s"] - expected_end, 6),
        })
    extras = [detected[index] for index in range(len(detected)) if index not in used]
    if extras:
        raise MidiError(f"notas não previstas, inclusive em silêncio: {extras}")
    return pairs


def _transcribe(source: Path, out: Path) -> dict:
    from importlib.metadata import version
    import basic_pitch
    from basic_pitch.inference import predict

    model = Path(basic_pitch.__file__).parent / MODEL_RELATIVE
    digest = verify_model(model, version("basic-pitch"))
    try:
        _output, midi, events = predict(str(source), **PARAMETERS)
    except Exception as exc:
        raise MidiError(f"basic-pitch não transcreveu: {type(exc).__name__}: {exc}") from exc
    if not events:
        raise MidiError("transcrição sem notas")
    midi_path = out.with_suffix(".mid")
    midi.write(str(midi_path))
    parsed = parse_midi_notes(midi_path)
    if not parsed:
        midi_path.unlink(missing_ok=True)
        raise MidiError("MIDI escrito sem notas legíveis")
    notes = [
        {
            "start_s": round(float(event[0]), 6),
            "end_s": round(float(event[1]), 6),
            "pitch": int(event[2]),
            "amplitude": round(float(event[3]), 6),
        }
        for event in events
    ]
    return {
        "schema": "fyah-re/midi-transcribe@1",
        "ok": True,
        "tool": "basic-pitch",
        "tool_version": PINNED_VERSION,
        "license": LICENSE,
        "model": {"path": MODEL_RELATIVE.as_posix(), "sha256": digest, "origin": MODEL_ORIGIN},
        "parameters": {key: value for key, value in PARAMETERS.items() if value is not None},
        "midi": midi_path.name,
        "note_count": len(parsed),
        "notes": notes,
        "limitations": LIMITATIONS,
    }


def transcribe_file(path: str, out: str) -> dict:
    source = Path(path)
    destination = Path(out)
    if not source.is_file():
        raise MidiError(f"arquivo não encontrado: {path}")
    if source.stat().st_size == 0:
        raise MidiError("entrada vazia")
    if importlib.util.find_spec("basic_pitch") is None:
        raise MidiError("basic-pitch ausente; use a venv isolada FYAH_RE_VENVS/basicpitch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        return _transcribe(source, destination)
    except Exception:
        destination.with_suffix(".mid").unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise


def main(argv=None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="python -m audio.midi_transcribe")
    parser.add_argument("audio")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if os.environ.get("FYAH_MIDI_CHILD") != "1" and importlib.util.find_spec("basic_pitch") is None:
        python = _venv_python()
        if python is None:
            print("basic-pitch ausente; use a venv isolada FYAH_RE_VENVS/basicpitch", file=sys.stderr)
            return 1
        env = os.environ.copy()
        env["FYAH_MIDI_CHILD"] = "1"
        repo = str(Path(__file__).resolve().parents[2])
        env["PYTHONPATH"] = repo + os.pathsep + env.get("PYTHONPATH", "")
        completed = subprocess.run(
            [str(python), "-m", "audio.midi_transcribe", args.audio, "--out", args.out],
            env=env,
        )
        return completed.returncode
    try:
        result = transcribe_file(args.audio, args.out)
    except MidiError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    text = json.dumps(result, indent=2, ensure_ascii=False)
    Path(args.out).write_text(text + "\n")
    print(text)
    return 0

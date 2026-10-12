"""Transcrição local áudio→MIDI com basic-pitch ONNX. Sem API e sem GPU.

A oitava extra de uma série harmônica foi reproduzida e não foi filtrada.
O onset do modelo em MIDI 88 fica acima do limiar 0,5; o contorno dessa
ativação (0,327) é indistinguível do contorno da nota mais fraca numa díade
válida (0,333). Suprimir oitavas apagaria um A4+A5 realmente executado.
"""
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
# Defaults da biblioteca. Não foram alterados: mudar o limiar para apagar a
# oitava extra também aproximaria do onset da nota mais fraca da díade.
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
    "caso A passa só com três senoides isoladas; isso não é transcrição de música completa",
    "polifonia geral, instrumentos reais e pitch bend não foram aprovados",
    "tolerância fixa: ±1 semitom e ±80 ms, independente uma da outra",
    "pares alinhados compatíveis com harmônicos são bloqueados por padrão, sem apagar notas; a distinção pode exigir revisão humana",
    "FYAH_MIDI_ALLOW_HARMONIC_AMBIGUITY=1 permite saída bruta explicitamente, inclusive com risco de notas espúrias",
]


class MidiError(RuntimeError):
    """Transcription did not produce a trustworthy MIDI file."""


def harmonic_midi(fundamental: int, number: int) -> int:
    """Nearest MIDI pitch of harmonic N. Documents the partial; it is not a performed note."""
    return int(round(fundamental + 12 * math.log2(number)))


def _partials(fundamental_hz: float, fundamental_midi: int, name: str, start_s: float, duration_s: float, count: int, amplitudes: tuple[float, ...]) -> tuple[list[tuple[float, float]], tuple[dict, ...]]:
    partials = []
    described = []
    for number, amplitude in zip(range(1, count + 1), amplitudes):
        partials.append((fundamental_hz * number, amplitude))
        if number > 1:
            described.append({
                "name": f"{name} h{number}",
                "pitch": harmonic_midi(fundamental_midi, number),
                "start_s": start_s,
                "duration_s": duration_s,
                "harmonic": number,
                "fundamental": name,
            })
    return partials, tuple(described)


def _note(name: str, frequency_hz: float, pitch: int, start_s: float, duration_s: float, partials: tuple[tuple[float, float], ...] | None = None) -> dict:
    return {
        "name": name,
        "frequency_hz": frequency_hz,
        "pitch": pitch,
        "start_s": start_s,
        "duration_s": duration_s,
        "partials": partials or ((frequency_hz, 1.0),),
    }


def case_specs() -> dict[str, dict]:
    """References fixed before inference. Harmonic pitches describe energy in the file."""
    a = [_note(item["name"], item["frequency_hz"], item["pitch"], item["start_s"], item["duration_s"]) for item in REFERENCE_NOTES]
    b_notes = []
    b_partials: list[dict] = []
    for item, count, amplitudes in (
        (REFERENCE_NOTES[0], 4, (1.0, 0.5, 0.25, 0.12)),
        (REFERENCE_NOTES[1], 4, (1.0, 0.5, 0.25, 0.12)),
        (REFERENCE_NOTES[2], 4, (1.0, 0.5, 0.25, 0.12)),
    ):
        waves, described = _partials(item["frequency_hz"], item["pitch"], item["name"], item["start_s"], item["duration_s"], count, amplitudes)
        b_notes.append(_note(item["name"], item["frequency_hz"], item["pitch"], item["start_s"], item["duration_s"], tuple(waves)))
        b_partials.extend(described)
    c = [
        _note("A4", 440.0, 69, 0.40, 0.80),
        _note("E5", 659.25, 76, 0.40, 0.80),
    ]
    d_waves, d_partials = _partials(440.0, 69, "A4", 0.40, 1.20, 6, (1.0, 0.6, 0.35, 0.2, 0.12, 0.08))
    d = [_note("A4", 440.0, 69, 0.40, 1.20, tuple(d_waves))]
    e = [
        _note("A4", 440.0, 69, 0.70, 0.55),
        _note("C5", 523.25, 72, 2.00, 0.55),
        _note("E5", 659.25, 76, 3.30, 0.55),
    ]
    return {
        "A": {"id": "A", "title": "senoides isoladas", "expect": "PASS", "tail_s": 0.50, "notes": a, "partials": ()},
        "B": {"id": "B", "title": "série harmônica", "expect": "BLOCKED", "tail_s": 0.50, "notes": b_notes, "partials": tuple(b_partials)},
        "C": {"id": "C", "title": "duas senoides simultâneas", "expect": "PASS", "tail_s": 0.50, "notes": c, "partials": ()},
        "D": {"id": "D", "title": "timbre harmônico", "expect": "BLOCKED", "tail_s": 0.50, "notes": d, "partials": d_partials},
        "E": {"id": "E", "title": "silêncio antes, entre e depois", "expect": "PASS", "tail_s": 0.70, "notes": e, "partials": ()},
    }


def render_wav(path: str | Path, notes: list[dict], tail_s: float = REFERENCE_TAIL_S) -> None:
    destination = Path(path)
    total = max(note["start_s"] + note["duration_s"] for note in notes) + tail_s
    frames = [0.0] * int(SAMPLE_RATE * total)
    for note in notes:
        start = int(note["start_s"] * SAMPLE_RATE)
        length = int(note["duration_s"] * SAMPLE_RATE)
        for index in range(length):
            t = index / SAMPLE_RATE
            envelope = min(1.0, t / 0.02) * min(1.0, (note["duration_s"] - t) / 0.04)
            sample = 0.0
            for frequency, amplitude in note["partials"]:
                sample += amplitude * math.sin(2 * math.pi * frequency * t)
            frames[start + index] += 0.35 * envelope * sample
    peak = max(1e-9, max(abs(sample) for sample in frames))
    raw = bytearray()
    for sample in frames:
        value = int(max(-1.0, min(1.0, sample / peak * 0.8)) * 32767)
        raw.extend(value.to_bytes(2, "little", signed=True))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destination), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(raw)


def write_reference_wav(path: str | Path) -> None:
    spec = case_specs()["A"]
    render_wav(path, spec["notes"], spec["tail_s"])


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


def _pair(detected: list[dict], reference: list[dict]) -> tuple[list[dict], list[str], list[dict]]:
    used: set[int] = set()
    pairs = []
    missing = []
    for item in reference:
        expected_end = item["start_s"] + item["duration_s"]
        found = None
        for index, note in enumerate(detected):
            if index in used:
                continue
            if abs(note["pitch"] - item["pitch"]) > PITCH_TOLERANCE_SEMITONES:
                continue
            if abs(note["start_s"] - item["start_s"]) > ONSET_TOLERANCE_S:
                continue
            if abs(note["end_s"] - expected_end) > OFFSET_TOLERANCE_S:
                continue
            found = index
            break
        if found is None:
            missing.append(item["name"])
            continue
        used.add(found)
        note = detected[found]
        pairs.append({
            "name": item["name"],
            "pitch": note["pitch"],
            "expected_pitch": item["pitch"],
            "onset_error_s": round(note["start_s"] - item["start_s"], 6),
            "offset_error_s": round(note["end_s"] - expected_end, 6),
        })
    extras = [detected[index] for index in range(len(detected)) if index not in used]
    return pairs, missing, extras


def match_reference(detected: list[dict], reference: list[dict] | None = None) -> list[dict]:
    """Pair every reference note and reject any extra note, including notes in the gaps."""
    pairs, missing, extras = _pair(detected, list(REFERENCE_NOTES if reference is None else reference))
    if missing:
        raise MidiError(f"nota de referência sem correspondência: {missing[0]}")
    if extras:
        raise MidiError(f"notas não previstas, inclusive em silêncio: {extras}")
    return pairs


def _public_note(note: dict) -> dict:
    return {
        "pitch": note["pitch"],
        "start_s": round(float(note["start_s"]), 6),
        "end_s": round(float(note["end_s"]), 6),
    }


def evaluate_notes(detected: list[dict], reference: list[dict], partials: list[dict] | tuple = ()) -> dict:
    """Score pitch and time separately. A harmonic partial is not promoted to a performed note."""
    pairs, missing, extras = _pair(detected, reference)
    harmonic = []
    unrelated = []
    for note in extras:
        match = None
        for partial in partials:
            overlaps = note["end_s"] >= partial["start_s"] - ONSET_TOLERANCE_S and note["start_s"] <= partial["start_s"] + partial["duration_s"] + OFFSET_TOLERANCE_S
            if overlaps and abs(note["pitch"] - partial["pitch"]) <= PITCH_TOLERANCE_SEMITONES:
                match = partial
                break
        public = _public_note(note)
        if match is None:
            unrelated.append(public)
        else:
            public["partial"] = match["name"]
            public["partial_pitch"] = match["pitch"]
            harmonic.append(public)
    status = "PASS" if not missing and not extras else "FAIL"
    return {
        "status": status,
        "matched": pairs,
        "missing": missing,
        "harmonic_confusions": harmonic,
        "unrelated_extras": unrelated,
        "tolerances": {
            "pitch_semitones": PITCH_TOLERANCE_SEMITONES,
            "onset_s": ONSET_TOLERANCE_S,
            "offset_s": OFFSET_TOLERANCE_S,
        },
    }



def harmonic_ambiguities(notes: list[dict]) -> list[dict]:
    """Return aligned note pairs that may be a fundamental plus its harmonic partial.

    This deliberately does not delete notes. A real octave/chord can be
    acoustically indistinguishable from a harmonic partial, so callers must
    fail closed or explicitly opt into the unfiltered Basic Pitch output.
    """
    candidates = []
    ordered = sorted(notes, key=lambda note: (int(note["pitch"]), float(note["start_s"])))
    for index, lower in enumerate(ordered):
        lower_pitch = int(lower["pitch"])
        lower_start = float(lower["start_s"])
        lower_end = float(lower["end_s"])
        lower_duration = max(0.0, lower_end - lower_start)
        if lower_duration <= 0:
            continue
        for upper in ordered[index + 1:]:
            upper_pitch = int(upper["pitch"])
            semitones = upper_pitch - lower_pitch
            if semitones < 12:
                continue
            harmonic_number = int(round(2 ** (semitones / 12.0)))
            if not 2 <= harmonic_number <= 8:
                continue
            expected_semitones = 12.0 * math.log2(harmonic_number)
            if abs(semitones - expected_semitones) > PITCH_TOLERANCE_SEMITONES:
                continue
            upper_start = float(upper["start_s"])
            upper_end = float(upper["end_s"])
            upper_duration = max(0.0, upper_end - upper_start)
            if upper_duration <= 0 or abs(upper_start - lower_start) > ONSET_TOLERANCE_S:
                continue
            overlap = max(0.0, min(lower_end, upper_end) - max(lower_start, upper_start))
            if overlap < 0.60 * min(lower_duration, upper_duration):
                continue
            candidate = {
                "lower_pitch": lower_pitch,
                "upper_pitch": upper_pitch,
                "harmonic_number": harmonic_number,
            }
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


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
    notes = [
        {
            "start_s": round(float(event[0]), 6),
            "end_s": round(float(event[1]), 6),
            "pitch": int(event[2]),
            "amplitude": round(float(event[3]), 6),
        }
        for event in events
    ]
    ambiguities = harmonic_ambiguities(notes)
    allow_ambiguity = os.environ.get("FYAH_MIDI_ALLOW_HARMONIC_AMBIGUITY") == "1"
    if ambiguities and not allow_ambiguity:
        details = ", ".join(
            f"MIDI {item['upper_pitch']} pode ser parcial h{item['harmonic_number']} de MIDI {item['lower_pitch']}"
            for item in ambiguities
        )
        raise MidiError(
            "transcrição bloqueada: ambiguidade harmônica não resolvida ("
            + details
            + "). Nenhum MIDI foi publicado. Revise a fonte ou defina "
            + "FYAH_MIDI_ALLOW_HARMONIC_AMBIGUITY=1 para aceitar explicitamente a saída bruta."
        )
    midi_path = out.with_suffix(".mid")
    midi.write(str(midi_path))
    parsed = parse_midi_notes(midi_path)
    if not parsed:
        midi_path.unlink(missing_ok=True)
        raise MidiError("MIDI escrito sem notas legíveis")
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
        "harmonic_ambiguities": ambiguities,
        "harmonic_ambiguity_override": allow_ambiguity,
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

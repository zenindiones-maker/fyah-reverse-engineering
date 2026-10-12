"""Evidência acústica de oitava tocada contra segundo harmônico.

As fixtures O e O-h atuais usam o mesmo envelope. A correlação das bandas
é 1 e o onset coincide, então não há base para PASS. Um par só deixa de
ser ambíguo quando o próprio áudio mostra um onset separado.
"""
import math
import wave
from pathlib import Path

from audio.midi_transcribe import (
    HARMONIC_INTERVAL_TOLERANCE_SEMITONES,
    ONSET_TOLERANCE_S,
    SAMPLE_RATE,
    _note,
    case_specs,
    evaluate_notes,
    harmonic_ambiguities,
    measure_pair_evidence,
    render_wav,
    resolve_harmonic_ambiguities,
)


def _frames(path: Path) -> list[float]:
    with wave.open(str(path), "rb") as wav:
        raw = wav.readframes(wav.getnframes())
    return [int.from_bytes(raw[i:i + 2], "little", signed=True) / 32768 for i in range(0, len(raw), 2)]


def test_identical_octave_and_partial_stay_ambiguous(tmp_path):
    played = case_specs()["O"]
    partial = [_note("A4", 440.0, 69, 0.40, 0.80, ((440.0, 1.0), (880.0, 0.8)))]
    left = tmp_path / "O.wav"
    right = tmp_path / "Oh.wav"
    render_wav(left, played["notes"], played["tail_s"])
    render_wav(right, partial, 0.50)
    assert _frames(left) == _frames(right)
    aligned = [
        {"pitch": 69, "start_s": 0.406, "end_s": 1.231},
        {"pitch": 81, "start_s": 0.406, "end_s": 1.149},
    ]
    evidence = measure_pair_evidence(left, 69, 81)
    assert evidence["envelope_correlation"] > 0.99
    assert abs(evidence["onset_delta_s"]) <= 0.08
    decision = resolve_harmonic_ambiguities(left, aligned, evidence)
    assert decision["status"] == "BLOCKED"
    assert decision["removed"] == []
    assert {note["pitch"] for note in decision["notes"]} == {69, 81}
    assert "indistingu" in decision["reason"]


def test_same_envelope_amplitude_change_does_not_create_a_note():
    notes = [
        {"pitch": 69, "start_s": 0.40, "end_s": 1.20},
        {"pitch": 81, "start_s": 0.40, "end_s": 1.20},
    ]
    for ratio in (0.04, 0.16, 0.64, 1.6):
        decision = resolve_harmonic_ambiguities(
            Path("unused.wav"),
            notes,
            {"onset_delta_s": 0.0, "envelope_correlation": 1.0, "band_ratio": ratio},
        )
        assert decision["status"] == "BLOCKED"
        assert decision["removed"] == []


def test_independent_offset_keeps_both_pitches_and_is_not_a_partial():
    separated = [
        {"pitch": 69, "start_s": 0.40, "end_s": 1.20},
        {"pitch": 81, "start_s": 0.40 + 0.12, "end_s": 1.32},
    ]
    assert harmonic_ambiguities(separated) == []
    decision = resolve_harmonic_ambiguities(
        Path("unused.wav"),
        separated,
        {"onset_delta_s": 0.151, "envelope_correlation": 0.676, "band_ratio": 0.64},
    )
    assert decision["status"] == "PASS"
    assert decision["removed"] == []
    assert [note["pitch"] for note in decision["notes"]] == [69, 81]
    assert decision["reason"] == "onset independente"


def test_offset_inside_gate_stays_blocked():
    close = [
        {"pitch": 69, "start_s": 0.40, "end_s": 1.20},
        {"pitch": 81, "start_s": 0.45, "end_s": 1.25},
    ]
    assert harmonic_ambiguities(close)
    decision = resolve_harmonic_ambiguities(
        Path("unused.wav"),
        close,
        {"onset_delta_s": 0.046, "envelope_correlation": 0.906, "band_ratio": 0.64},
    )
    assert decision["status"] == "BLOCKED"
    assert decision["removed"] == []


def test_phase_lock_does_not_delete_the_octave_pitch(tmp_path):
    """A phase-locked 880 Hz partial is the same waveform as two sines."""
    tone = [_note("A4", 440.0, 69, 0.40, 0.80, ((440.0, 1.0), (880.0, 0.35)))]
    path = tmp_path / "locked.wav"
    render_wav(path, tone, 0.50)
    detected = [
        {"pitch": 69, "start_s": 0.406, "end_s": 1.231, "amplitude": 0.77},
        {"pitch": 81, "start_s": 0.406, "end_s": 1.149, "amplitude": 0.30},
    ]
    decision = resolve_harmonic_ambiguities(
        path,
        detected,
        {"onset_delta_s": 0.0, "envelope_correlation": 1.0, "band_ratio": 0.1225, "phase_locked": True},
    )
    assert decision["status"] == "BLOCKED"
    assert decision["removed"] == []
    assert {note["pitch"] for note in decision["notes"]} == {69, 81}
    assert decision["published_as_independent"] == []


def test_phase_lock_is_not_enough_when_the_waveform_matches_two_sines(tmp_path):
    played = case_specs()["O"]
    path = tmp_path / "O.wav"
    render_wav(path, played["notes"], played["tail_s"])
    detected = [
        {"pitch": 69, "start_s": 0.406, "end_s": 1.231},
        {"pitch": 81, "start_s": 0.406, "end_s": 1.149},
    ]
    decision = resolve_harmonic_ambiguities(
        path,
        detected,
        {"onset_delta_s": 0.0, "envelope_correlation": 1.0, "band_ratio": 0.64, "phase_locked": True},
    )
    assert decision["status"] == "BLOCKED"
    assert 81 in {note["pitch"] for note in decision["notes"]}


def test_noise_and_short_audio_without_a_gap_stay_blocked():
    notes = [
        {"pitch": 69, "start_s": 0.40, "end_s": 1.20},
        {"pitch": 81, "start_s": 0.40, "end_s": 1.20},
    ]
    noisy = resolve_harmonic_ambiguities(
        Path("unused.wav"),
        notes,
        {"onset_delta_s": 0.0, "envelope_correlation": 1.0, "band_ratio": 0.64, "snr_db": 8.0},
    )
    unread = resolve_harmonic_ambiguities(
        Path("unused.wav"),
        notes,
        {"onset_delta_s": None, "envelope_correlation": None, "band_ratio": None},
    )
    assert noisy["status"] == "BLOCKED"
    assert unread["status"] == "BLOCKED"
    assert "insuficiente" in unread["reason"]


def test_thirteen_semitone_dyad_is_outside_the_harmonic_gate():
    dyad = [
        {"pitch": 69, "start_s": 0.40, "end_s": 1.20},
        {"pitch": 82, "start_s": 0.40, "end_s": 1.20},
    ]
    assert harmonic_ambiguities(dyad) == []
    assert HARMONIC_INTERVAL_TOLERANCE_SEMITONES == 0.5
    assert ONSET_TOLERANCE_S == 0.08


def test_render_can_shift_one_partial_without_changing_the_other(tmp_path):
    notes = [_note("A4", 440.0, 69, 0.40, 0.80, ((440.0, 1.0), (880.0, 0.8)))]
    notes[0]["partial_delay_s"] = {880.0: 0.12}
    path = tmp_path / "delayed.wav"
    render_wav(path, notes, 0.20)
    frames = _frames(path)
    start = int(0.40 * SAMPLE_RATE)
    early = frames[start:start + int(0.05 * SAMPLE_RATE)]
    sign_changes = sum(left * right < 0 for left, right in zip(early, early[1:]))
    expected = 0.05 * 440 * 2
    assert abs(sign_changes - expected) < 8
    assert math.isfinite(sum(frames))


def test_audio_onset_above_80ms_keeps_every_model_note(tmp_path):
    played = [
        _note("A4", 440.0, 69, 0.40, 0.80),
        _note("A5", 880.0, 81, 0.55, 0.80, ((880.0, 0.8),)),
    ]
    path = tmp_path / "offset.wav"
    render_wav(path, played, 0.50)
    evidence = measure_pair_evidence(path, 69, 81)
    assert evidence["onset_delta_s"] > 0.08
    glued = [
        {"pitch": 69, "start_s": 0.546, "end_s": 1.231},
        {"pitch": 81, "start_s": 0.557, "end_s": 1.347},
        {"pitch": 69, "start_s": 0.395, "end_s": 0.546},
    ]
    assert harmonic_ambiguities(glued)
    decision = resolve_harmonic_ambiguities(path, glued, evidence)
    assert decision["status"] == "PASS"
    assert decision["removed"] == []
    assert sorted(note["pitch"] for note in decision["notes"]) == [69, 69, 81]
    assert decision["reason"] == "onset independente no áudio"


def test_contiguous_fragments_cover_one_reference_without_merging_a_gap():
    reference = [_note("A4", 440.0, 69, 0.40, 0.80), _note("A5", 880.0, 81, 0.55, 0.80, ((880.0, 0.8),))]
    detected = [
        {"pitch": 69, "start_s": 0.395, "end_s": 0.546},
        {"pitch": 69, "start_s": 0.546, "end_s": 1.230},
        {"pitch": 81, "start_s": 0.557, "end_s": 1.347},
    ]
    score = evaluate_notes(detected, reference, ())
    assert score["status"] == "PASS"
    assert score["missing"] == []
    assert score["unrelated_extras"] == []
    gapped = [
        {"pitch": 69, "start_s": 0.40, "end_s": 0.70},
        {"pitch": 69, "start_s": 0.90, "end_s": 1.20},
    ]
    split = evaluate_notes(gapped, [_note("A4", 440.0, 69, 0.40, 0.80)], ())
    assert split["status"] == "FAIL"

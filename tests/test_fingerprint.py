import hashlib
import json
import math
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from audio.fingerprint import FingerprintError, fingerprint_file


def _tone(path: Path, seconds: float = 5.0, amplitude: int = 8000) -> None:
    rate = 22050
    frames = bytearray()
    for i in range(int(rate * seconds)):
        value = int(amplitude * math.sin(2 * math.pi * 440 * i / rate))
        frames.extend(value.to_bytes(2, "little", signed=True))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(frames)


def _silence(path: Path) -> None:
    rate = 22050
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * rate * 2)


def test_fingerprint_cli_hashes_a_real_local_chromaprint(tmp_path):
    if shutil.which("fpcalc") is None:
        pytest.fail("fpcalc ausente; instale libchromaprint-tools antes de declarar fingerprint")
    source = tmp_path / "tone.wav"
    _tone(source)
    output = tmp_path / "fingerprint.json"
    result = subprocess.run(
        [sys.executable, "-m", "tools", "run", "fingerprint", "--input", str(source), "--out", str(output)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text())
    assert payload["schema"] == "fyah-re/fingerprint@1"
    assert payload["ok"] is True
    assert payload["lookup"] is False
    assert payload["algorithm"] == "chromaprint"
    assert payload["fingerprint"].strip()
    assert payload["duration_s"] == 5.0
    assert "fpcalc" in payload["fpcalc_version"]
    again = fingerprint_file(str(source))
    assert again["fingerprint"] == payload["fingerprint"]
    receipt = json.loads((tmp_path / "fingerprint.json.receipt.json").read_text())
    assert receipt["status"] == "success"
    assert receipt["tool_name"] == "fingerprint"
    assert receipt["tool_version"] == "1"
    assert receipt["output_artifacts"][0]["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    joined = json.dumps(payload)
    assert "http://" not in joined and "https://" not in joined


def test_silence_empty_and_corrupt_do_not_invent_a_fingerprint(tmp_path, monkeypatch):
    silence = tmp_path / "silence.wav"
    _silence(silence)
    with pytest.raises(FingerprintError, match="silêncio"):
        fingerprint_file(str(silence))
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(FingerprintError, match="vazia"):
        fingerprint_file(str(empty))
    corrupt = tmp_path / "corrupt.wav"
    corrupt.write_bytes(b"not a wav")
    if shutil.which("fpcalc") is None:
        pytest.fail("fpcalc ausente; o caso corrompido precisa do binário real")
    with pytest.raises(FingerprintError, match="não produzido"):
        fingerprint_file(str(corrupt))
    output = tmp_path / "silence.json"
    result = subprocess.run(
        [sys.executable, "-m", "tools", "run", "fingerprint", "--input", str(silence), "--out", str(output)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert not output.exists()
    receipt = json.loads((tmp_path / "silence.json.receipt.json").read_text())
    assert receipt["status"] == "failed"
    assert receipt["output_artifacts"] == []
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(FingerprintError, match="fpcalc ausente"):
        fingerprint_file(str(silence))

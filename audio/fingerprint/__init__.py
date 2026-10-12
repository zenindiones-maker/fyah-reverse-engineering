"""Fingerprint acústico local com Chromaprint/fpcalc. Sem lookup e sem rede."""
from __future__ import annotations

import json
import shutil
import subprocess
import wave
from array import array
from pathlib import Path

# fpcalc 1.5.x reports this on the final decoder frame and still prints a fingerprint.
_BENIGN_EOF = "ERROR: Error decoding audio frame (End of file)"


class FingerprintError(RuntimeError):
    """The fingerprint was not produced. Callers must not invent one."""


def _fpcalc_version() -> str:
    completed = subprocess.run(["fpcalc", "-version"], capture_output=True, text=True)
    line = (completed.stdout or completed.stderr or "").strip().splitlines()
    return line[0] if line else "fpcalc"


def _wav_problem(path: Path) -> str | None:
    """Reject empty or digital-silence WAV before fpcalc. Other formats return None."""
    try:
        with wave.open(str(path), "rb") as wav:
            frames = wav.getnframes()
            width = wav.getsampwidth()
            rate = wav.getframerate()
            if frames <= 0 or width <= 0 or rate <= 0:
                return "entrada vazia"
            if width not in (1, 2):
                return None
            peak = 0
            remaining = frames
            while remaining:
                chunk = min(remaining, 65536)
                raw = wav.readframes(chunk)
                remaining -= chunk
                if width == 1:
                    peak = max(peak, max((abs(b - 128) for b in raw), default=0))
                else:
                    samples = array("h")
                    samples.frombytes(raw[: len(raw) // 2 * 2])
                    peak = max(peak, max((abs(sample) for sample in samples), default=0))
                if peak:
                    return None
            return "silêncio inválido"
    except (wave.Error, EOFError):
        return None


def _stderr_is_benign(stderr: str) -> bool:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return all(line == _BENIGN_EOF for line in lines)


def fingerprint_file(path: str) -> dict:
    source = Path(path)
    if not source.is_file():
        raise FingerprintError(f"arquivo não encontrado: {path}")
    if source.stat().st_size == 0:
        raise FingerprintError("entrada vazia")
    if shutil.which("fpcalc") is None:
        raise FingerprintError("fpcalc ausente; instale libchromaprint-tools")
    problem = _wav_problem(source)
    if problem:
        raise FingerprintError(problem)
    completed = subprocess.run(
        ["fpcalc", "-json", str(source)],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(completed.stdout) if completed.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        raise FingerprintError("fpcalc não devolveu JSON") from exc
    fingerprint = payload.get("fingerprint")
    duration = payload.get("duration")
    warning = completed.stderr.strip() or None
    usable = (
        isinstance(fingerprint, str)
        and bool(fingerprint.strip())
        and isinstance(duration, (int, float))
        and float(duration) > 0
        and (completed.returncode == 0 or (completed.returncode == 3 and _stderr_is_benign(completed.stderr)))
    )
    if not usable:
        detail = warning or f"fpcalc exit {completed.returncode}"
        raise FingerprintError(f"fingerprint não produzido: {detail}")
    return {
        "schema": "fyah-re/fingerprint@1",
        "ok": True,
        "algorithm": "chromaprint",
        "license": "Expat",
        "fpcalc_version": _fpcalc_version(),
        "fingerprint": fingerprint,
        "duration_s": float(duration),
        "lookup": False,
        "fpcalc_exit_code": completed.returncode,
        "fpcalc_warning": warning,
        "source": source.name,
    }


def main(argv=None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="python -m audio.fingerprint")
    parser.add_argument("audio")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        result = fingerprint_file(args.audio)
    except FingerprintError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        destination = Path(args.out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text + "\n")
    print(text)
    return 0

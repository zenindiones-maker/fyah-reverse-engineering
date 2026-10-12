"""Real CLI E2E: exercise ffprobe, JSON output, and the persisted execution receipt."""
import hashlib
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path


def _run_media_inspect(source: Path, output: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable, "-m", "tools", "run", "media-inspect",
            "--input", str(source), "--out", str(output),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_media_inspect_cli_writes_real_output_and_matching_receipt(tmp_path):
    assert shutil.which("ffprobe"), "ffprobe must be available for the real media-inspect E2E"

    source = tmp_path / "synthetic.wav"
    with wave.open(str(source), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 8000)

    output = tmp_path / "media.json"
    result = _run_media_inspect(source, output)

    assert result.returncode == 0, f"CLI failed: {result.stdout}\n{result.stderr}"
    assert output.is_file(), "CLI did not create the media-inspect JSON"
    payload = json.loads(output.read_text())
    assert payload["schema"] == "fyah-re/media-inspect@1"
    assert payload["ok"] is True
    streams = payload["ffprobe"]["streams"]
    assert streams and streams[0]["codec_type"] == "audio"

    receipt_path = tmp_path / "media.json.receipt.json"
    assert receipt_path.is_file(), "CLI did not persist its execution receipt"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["schema_version"] == "fyah-re/execution-receipt@1"
    assert receipt["status"] == "success"
    assert receipt["exit_code"] == 0
    assert receipt["tool_name"] == "media-inspect"
    assert receipt["output_artifacts"][0]["path"] == "media.json"
    assert receipt["output_artifacts"][0]["size_bytes"] == output.stat().st_size
    assert receipt["output_artifacts"][0]["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert str(tmp_path) not in json.dumps(receipt["output_artifacts"])


def test_media_inspect_cli_records_real_ffprobe_failure(tmp_path):
    assert shutil.which("ffprobe"), "ffprobe must be available for the real media-inspect E2E"

    source = tmp_path / "not-media.bin"
    source.write_bytes(b"this is deliberately not a valid audio or video file")
    output = tmp_path / "failed.json"

    result = _run_media_inspect(source, output)

    assert result.returncode != 0, "invalid media unexpectedly passed ffprobe"
    assert not output.exists(), "failed media inspection must not leave a success artifact"
    receipt_path = tmp_path / "failed.json.receipt.json"
    assert receipt_path.is_file(), "failed execution did not persist a receipt"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["schema_version"] == "fyah-re/execution-receipt@1"
    assert receipt["status"] == "failed"
    assert receipt["exit_code"] != 0
    assert receipt["error_category"] == "CalledProcessError"
    assert receipt["output_artifacts"] == []

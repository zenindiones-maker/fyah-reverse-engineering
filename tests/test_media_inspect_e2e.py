"""Real CLI E2E: exercise ffprobe, HTTP download, JSON output, and receipts."""
import hashlib
import json
import shutil
import subprocess
import sys
import threading
import wave
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from functools import partial


def _run_media_inspect(source: str | Path, output: Path) -> subprocess.CompletedProcess:
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


def _make_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 8000)


def test_media_inspect_cli_writes_real_output_and_matching_receipt(tmp_path):
    assert shutil.which("ffprobe"), "ffprobe must be available for the real media-inspect E2E"
    source = tmp_path / "synthetic.wav"
    _make_wav(source)
    output = tmp_path / "media.json"

    result = _run_media_inspect(source, output)

    assert result.returncode == 0, f"CLI failed: {result.stdout}\\n{result.stderr}"
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


def test_media_inspect_cli_downloads_from_http_url_and_records_receipt(tmp_path):
    assert shutil.which("ffprobe"), "ffprobe must be available for the real media-inspect E2E"
    source = tmp_path / "served.wav"
    _make_wav(source)

    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/served.wav"
        output = tmp_path / "downloaded-media.json"
        result = _run_media_inspect(url, output)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.returncode == 0, f"URL pipeline failed: {result.stdout}\\n{result.stderr}"
    payload = json.loads(output.read_text())
    assert payload["schema"] == "fyah-re/media-inspect@1"
    assert payload["ok"] is True
    assert payload["ffprobe"]["streams"][0]["codec_type"] == "audio"

    receipt = json.loads((tmp_path / "downloaded-media.json.receipt.json").read_text())
    assert receipt["status"] == "success"
    assert receipt["input_metadata"][0]["kind"] == "url"
    assert receipt["output_artifacts"][0]["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


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

"""Real CLI E2E: exercise ffprobe, HTTP download, JSON output, and receipts."""
import hashlib
import json
import math
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



def test_media_inspect_cli_downloads_public_wikimedia_media_url(tmp_path):
    """Exercise the same URL pipeline against a real public media host."""
    assert shutil.which("ffprobe"), "ffprobe must be available for the real media-inspect E2E"
    url = "https://upload.wikimedia.org/wikipedia/commons/4/40/Toreador_song_cleaned.ogg"
    output = tmp_path / "remote-media.json"

    result = _run_media_inspect(url, output)

    assert result.returncode == 0, f"remote URL pipeline failed: {result.stdout}\\n{result.stderr}"
    assert output.is_file(), "remote URL pipeline did not create JSON output"
    payload = json.loads(output.read_text())
    assert payload["schema"] == "fyah-re/media-inspect@1"
    assert payload["ok"] is True
    assert payload["ffprobe"]["streams"], "ffprobe found no streams in the downloaded public media"

    receipt = json.loads((tmp_path / "remote-media.json.receipt.json").read_text())
    assert receipt["schema_version"] == "fyah-re/execution-receipt@1"
    assert receipt["status"] == "success"
    assert receipt["exit_code"] == 0
    assert receipt["input_metadata"][0]["kind"] == "url"
    assert receipt["output_artifacts"][0]["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


class _DownloadFailureHandler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        if self.path == "/missing.wav":
            self.send_error(404, "deliberate E2E missing file")
            return
        if self.path == "/truncated.wav":
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", "1000")
            self.end_headers()
            self.wfile.write(b"short")
            self.wfile.flush()
            self.close_connection = True
            return
        if self.path == "/oversized.wav":
            self.send_response(200)
            self.send_header("Content-Length", str(2 * 1024 * 1024 * 1024 + 1))
            self.end_headers()
            self.close_connection = True
            return
        self.send_error(404)

    def log_message(self, format, *args):
        pass


def _run_failure_url_case(tmp_path, route):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _DownloadFailureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    output = tmp_path / f"{route.strip('/').replace('/', '-')}.json"
    try:
        url = f"http://127.0.0.1:{server.server_port}{route}"
        result = _run_media_inspect(url, output)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert result.returncode != 0, f"broken download unexpectedly passed: {route}"
    assert not output.exists(), "failed download must not leave a success artifact"
    receipt_path = output.with_name(output.name + ".receipt.json")
    assert receipt_path.is_file(), "failed download did not persist an execution receipt"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["schema_version"] == "fyah-re/execution-receipt@1"
    assert receipt["status"] == "failed"
    assert receipt["exit_code"] != 0
    assert receipt["output_artifacts"] == []
    assert receipt["input_metadata"][0]["kind"] == "url"
    return receipt


def test_media_inspect_cli_records_http_404_and_no_artifact(tmp_path):
    receipt = _run_failure_url_case(tmp_path, "/missing.wav")
    assert receipt["error_category"] == "HTTPError"


def test_media_inspect_cli_records_interrupted_download_and_no_artifact(tmp_path):
    receipt = _run_failure_url_case(tmp_path, "/truncated.wav")
    assert receipt["error_category"] == "DownloadIntegrityError"


def test_media_inspect_cli_rejects_oversized_content_length_before_download(tmp_path):
    receipt = _run_failure_url_case(tmp_path, "/oversized.wav")
    assert receipt["error_category"] == "ValueError"


def test_unified_cli_runs_real_audio_profile_and_receipts_output(tmp_path):
    """Prove the shared dispatcher reaches the real audio analyzer, not just media-inspect."""
    sample_rate = 22050
    frames = bytearray()
    for i in range(sample_rate * 4):
        value = int(10000 * math.sin(2 * math.pi * 440 * i / sample_rate))
        frames.extend(value.to_bytes(2, "little", signed=True))
    source = tmp_path / "tone.wav"
    with wave.open(str(source), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)

    output = tmp_path / "audio-profile.json"
    result = subprocess.run(
        [sys.executable, "-m", "tools", "run", "audio-profile",
         "--input", str(source), "--out", str(output)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, f"audio-profile CLI failed: {result.stdout}\\n{result.stderr}"
    payload = json.loads(output.read_text())
    assert payload["schema"] == "fyah-re/audio-profile@1"
    assert payload["duration_s"] == 4.0
    assert payload["sample_rate"] == sample_rate
    assert payload["spectrum"]["centroid_hz"] > 0
    receipt = json.loads((tmp_path / "audio-profile.json.receipt.json").read_text())
    assert receipt["schema_version"] == "fyah-re/execution-receipt@1"
    assert receipt["status"] == "success"
    assert receipt["tool_name"] == "audio-profile"
    assert receipt["output_artifacts"][0]["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


def test_unified_cli_runs_real_video_pacing_and_receipts_output(tmp_path):
    """Prove the shared dispatcher reaches PySceneDetect on a generated real video."""
    import numpy as np
    import pytest

    cv2 = pytest.importorskip("cv2")
    source = tmp_path / "scene-changes.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 10, (64, 48))
    assert writer.isOpened(), "OpenCV MP4 writer is unavailable in the CI environment"
    rng = np.random.default_rng(7)
    for _scene in range(4):
        frame = rng.integers(0, 255, (48, 64, 3), dtype=np.uint8)
        for _ in range(20):
            writer.write(frame)
    writer.release()

    output = tmp_path / "cuts-pacing.json"
    result = subprocess.run(
        [sys.executable, "-m", "tools", "run", "cuts-pacing",
         "--input", str(source), "--out", str(output)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, f"cuts-pacing CLI failed: {result.stdout}\\n{result.stderr}"
    payload = json.loads(output.read_text())
    assert payload["schema"] == "fyah-re/video-pacing@1"
    assert payload["duration_s"] >= 7.5
    assert payload["shots"] >= 2
    receipt = json.loads((tmp_path / "cuts-pacing.json.receipt.json").read_text())
    assert receipt["schema_version"] == "fyah-re/execution-receipt@1"
    assert receipt["status"] == "success"
    assert receipt["tool_name"] == "cuts-pacing"
    assert receipt["output_artifacts"][0]["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()



def test_media_inspect_runs_when_optional_mediainfo_binary_is_missing(tmp_path, monkeypatch):
    """The required ffprobe path must work even if the optional mediainfo CLI is absent."""
    from tools import __main__ as cli

    source = tmp_path / "without-mediainfo.wav"
    _make_wav(source)
    output = tmp_path / "without-mediainfo.json"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    original_which = shutil.which
    monkeypatch.setattr(
        cli.shutil,
        "which",
        lambda command: None if command == "mediainfo" else original_which(command),
    )

    result = cli._run_tool_with_tmp("media-inspect", [str(source)], output, workspace)

    assert result["ok"] is True
    assert result["ffprobe"]["streams"][0]["codec_type"] == "audio"
    assert "mediainfo" not in result
    assert json.loads(output.read_text())["ok"] is True



def test_er_analyze_workflow_adapter_uses_shared_cli_and_receipt(tmp_path):
    """Exercise the workflow's public entry point with a local HTTP-hosted media URL."""
    import os

    source = tmp_path / "workflow-source.wav"
    _make_wav(source)
    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    output_dir = tmp_path / "workflow-output"
    env = os.environ.copy()
    env["FYAH_RE_OUT_DIR"] = str(output_dir)
    env.pop("GITHUB_STEP_SUMMARY", None)
    try:
        url = f"http://127.0.0.1:{server.server_port}/workflow-source.wav"
        result = subprocess.run(
            [sys.executable, "scripts/er_analyze.py", "media-inspect", url, ""],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=45,
            env=env,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.returncode == 0, f"workflow adapter failed: {result.stdout}\\n{result.stderr}"
    output = output_dir / "media_inspect.json"
    assert json.loads(output.read_text())["schema"] == "fyah-re/media-inspect@1"
    receipt = json.loads((output_dir / "media_inspect.json.receipt.json").read_text())
    assert receipt["status"] == "success"
    assert receipt["input_metadata"][0]["kind"] == "url"



def test_er_analyze_compare_routes_two_real_urls_through_shared_cli(tmp_path):
    """Verify compare consumes both downloaded URLs and writes one hashed receipt."""
    import os

    sample_rate = 22050
    for filename, frequency, amplitude in (
        ("track-a.wav", 440, 9000),
        ("track-b.wav", 660, 5000),
    ):
        frames = bytearray()
        for i in range(sample_rate * 4):
            value = int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
            beat_phase = i % (sample_rate // 2)
            if beat_phase < 110:
                value += int(10000 * (1 - beat_phase / 110))
            value = max(-32768, min(32767, value))
            frames.extend(value.to_bytes(2, "little", signed=True))
        with wave.open(str(tmp_path / filename), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(frames)

    handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    output_dir = tmp_path / "compare-output"
    env = os.environ.copy()
    env["FYAH_RE_OUT_DIR"] = str(output_dir)
    env.pop("GITHUB_STEP_SUMMARY", None)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        result = subprocess.run(
            [sys.executable, "scripts/er_analyze.py", "compare",
             f"{base}/track-a.wav", f"{base}/track-b.wav"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=75,
            env=env,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.returncode == 0, f"compare workflow adapter failed: {result.stdout}\\n{result.stderr}"
    output = output_dir / "compare.json"
    payload = json.loads(output.read_text())
    assert payload["schema"] == "fyah-re/audio-compare@1"
    assert payload["tempo_bpm"]["a"] > 0
    assert payload["tempo_bpm"]["b"] > 0
    receipt = json.loads((output_dir / "compare.json.receipt.json").read_text())
    assert receipt["status"] == "success"
    assert len(receipt["input_metadata"]) == 2
    assert receipt["output_artifacts"][0]["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()

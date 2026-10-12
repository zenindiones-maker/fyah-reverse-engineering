
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from tools import __main__ as cli


def test_run_tool_writes_receipt_with_output_hash(tmp_path, monkeypatch):
    output = tmp_path / "result.json"

    def fake_execute(name, inputs, out):
        out.write_text(json.dumps({"ok": True, "schema": "test@1"}))
        return {"ok": True, "schema": "test@1"}

    monkeypatch.setattr(cli, "_run_tool", fake_execute)
    cli.run_tool("media-inspect", ["https://example.test/audio?token=secret"], output)

    receipt_path = tmp_path / "result.json.receipt.json"
    receipt = json.loads(receipt_path.read_text())
    artifact = output.read_bytes()

    assert receipt["schema_version"] == "fyah-re/execution-receipt@1"
    assert receipt["status"] == "success"
    assert receipt["exit_code"] == 0
    assert receipt["output_artifacts"][0]["sha256"] == hashlib.sha256(artifact).hexdigest()
    assert "secret" not in receipt_path.read_text()
    assert receipt["duration_ms"] >= 0


def test_run_tool_writes_failure_receipt_and_reraises(tmp_path, monkeypatch):
    output = tmp_path / "failed.json"

    def fake_execute(name, inputs, out):
        raise RuntimeError("execution failed")

    monkeypatch.setattr(cli, "_run_tool", fake_execute)
    with pytest.raises(RuntimeError, match="execution failed"):
        cli.run_tool("media-inspect", ["missing.wav"], output)

    receipt = json.loads((tmp_path / "failed.json.receipt.json").read_text())
    assert receipt["status"] == "failed"
    assert receipt["exit_code"] != 0
    assert receipt["error_category"] == "RuntimeError"


def test_run_tool_writes_blocked_receipt_and_reraises(tmp_path, monkeypatch):
    output = tmp_path / "blocked.json"

    def fake_execute(name, inputs, out):
        raise SystemExit("input rejected")

    monkeypatch.setattr(cli, "_run_tool", fake_execute)
    with pytest.raises(SystemExit, match="input rejected"):
        cli.run_tool("media-inspect", ["missing.wav"], output)

    receipt = json.loads((tmp_path / "blocked.json.receipt.json").read_text())
    assert receipt["status"] == "blocked"
    assert receipt["exit_code"] != 0
    assert receipt["error_category"] == "input_or_policy_rejection"


def test_missing_file_process_exit_matches_blocked_receipt(tmp_path):
    out = tmp_path / "F1.json"
    code = cli.main(["run", "midi-transcribe", "--input", str(tmp_path / "nao-existe.wav"), "--out", str(out)])
    receipt = json.loads((tmp_path / "F1.json.receipt.json").read_text())
    assert code == 2
    assert receipt["status"] == "blocked"
    assert receipt["exit_code"] == 2
    assert receipt["error_category"] == "input_or_policy_rejection"
    assert receipt["output_artifacts"] == []
    assert not out.exists()
    assert not out.with_suffix(".mid").exists()


def test_midi_exit_3_is_blocked_and_a_technical_exit_is_not(tmp_path, monkeypatch):
    wav = tmp_path / "tone.wav"
    wav.write_bytes(b"not-read")

    def boom(code):
        def fake_run(cmd, check=False, **kwargs):
            raise subprocess.CalledProcessError(code, cmd)
        return fake_run

    monkeypatch.setattr(cli.subprocess, "run", boom(3))
    blocked_out = tmp_path / "B.json"
    with pytest.raises(SystemExit) as exc:
        cli.run_tool("midi-transcribe", [str(wav)], blocked_out)
    assert exc.value.code == 3
    blocked = json.loads((tmp_path / "B.json.receipt.json").read_text())
    assert blocked["status"] == "blocked"
    assert blocked["exit_code"] == 3
    assert blocked["provenance"]["policy"] == "harmonic_ambiguity"
    assert blocked["output_artifacts"] == []
    assert not blocked_out.exists()
    assert not blocked_out.with_suffix(".mid").exists()

    monkeypatch.setattr(cli.subprocess, "run", boom(1))
    failed_out = tmp_path / "tech.json"
    with pytest.raises(subprocess.CalledProcessError):
        cli.run_tool("midi-transcribe", [str(wav)], failed_out)
    failed = json.loads((tmp_path / "tech.json.receipt.json").read_text())
    assert failed["status"] == "failed"
    assert "policy" not in failed["provenance"]
    assert failed["output_artifacts"] == []

    monkeypatch.setattr(cli.subprocess, "run", boom(3))
    other = tmp_path / "other.json"
    with pytest.raises(subprocess.CalledProcessError):
        cli.run_tool("fingerprint", [str(wav)], other)
    other_receipt = json.loads((tmp_path / "other.json.receipt.json").read_text())
    assert other_receipt["status"] == "failed"
    assert "policy" not in other_receipt["provenance"]



def test_pipeline_component_errors_are_detected_recursively():
    assert cli._contains_component_errors({"ok": True, "stems": {"error": "model missing"}})
    assert cli._contains_component_errors({"stages": [{"name": "decode", "error": "failed"}]})
    assert not cli._contains_component_errors({"ok": True, "profile": {"tempo_bpm": 120.0}})
    assert not cli._contains_component_errors({"ok": True, "optional": {"error": None}})


def test_partial_pipeline_output_is_failed_but_kept_in_receipt(tmp_path, monkeypatch):
    output = tmp_path / "partial.json"

    def fake_execute(name, inputs, out):
        payload = {"schema": "pipeline@1", "ok": False, "stems": {"error": "weights unavailable"}}
        out.write_text(json.dumps(payload))
        return payload

    monkeypatch.setattr(cli, "_run_tool", fake_execute)
    with pytest.raises(SystemExit) as exc:
        cli.run_tool("audio-full", ["owned.wav"], output)
    assert exc.value.code == 1
    assert output.is_file(), "partial diagnostics should remain available for debugging"

    receipt = json.loads((tmp_path / "partial.json.receipt.json").read_text())
    assert receipt["status"] == "failed"
    assert receipt["error_category"] == "ToolResultNotSuccessful"
    assert receipt["exit_code"] == 1
    assert receipt["output_artifacts"][0]["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()

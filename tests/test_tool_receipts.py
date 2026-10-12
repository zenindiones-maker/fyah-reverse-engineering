
import hashlib
import json
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

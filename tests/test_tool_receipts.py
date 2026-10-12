
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

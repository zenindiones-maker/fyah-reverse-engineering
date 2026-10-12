import hashlib
import json
from datetime import datetime, timezone

import pytest

from tools.contracts import ExecutionReceipt, artifact_metadata, build_receipt


def test_artifact_metadata_records_relative_path_size_and_sha256(tmp_path):
    artifact = tmp_path / "result.bin"
    artifact.write_bytes(b"fyah-receipt")

    metadata = artifact_metadata(artifact, root=tmp_path)

    assert metadata["path"] == "result.bin"
    assert metadata["size_bytes"] == len(b"fyah-receipt")
    assert metadata["sha256"] == hashlib.sha256(b"fyah-receipt").hexdigest()


def test_build_receipt_has_versioned_timestamps_duration_and_provenance():
    start = datetime(2026, 10, 12, 15, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 12, 15, 0, 2, tzinfo=timezone.utc)

    receipt = build_receipt(
        run_id="run-123",
        tool_name="media-inspect",
        tool_version="1.0",
        status="success",
        exit_code=0,
        started_at=start,
        ended_at=end,
        input_metadata=[{"name": "sample.wav", "sha256": "a" * 64}],
        output_artifacts=[],
        provenance={"source": "fyah-re", "commit": "b" * 40},
    )

    assert isinstance(receipt, ExecutionReceipt)
    payload = receipt.to_dict()
    assert payload["schema_version"] == "fyah-re/execution-receipt@1"
    assert payload["run_id"] == "run-123"
    assert payload["started_at"] == "2026-10-12T15:00:00Z"
    assert payload["ended_at"] == "2026-10-12T15:00:02Z"
    assert payload["duration_ms"] == 2000
    assert payload["status"] == "success"
    assert payload["exit_code"] == 0
    assert payload["provenance"]["commit"] == "b" * 40
    json.dumps(payload)


def test_receipt_rejects_unknown_status():
    with pytest.raises(ValueError, match="status"):
        build_receipt(
            run_id="run-123",
            tool_name="media-inspect",
            tool_version="1.0",
            status="maybe",
            exit_code=0,
            input_metadata=[],
            output_artifacts=[],
            provenance={},
        )


def test_receipt_sanitizes_signed_url_query_values():
    receipt = build_receipt(
        run_id="run-123",
        tool_name="media-inspect",
        tool_version="1.0",
        status="failed",
        exit_code=1,
        input_metadata=[{"url": "https://example.test/file?token=secret&X-Amz-Signature=private"}],
        output_artifacts=[],
        provenance={},
    )

    serialized = json.dumps(receipt.to_dict())
    assert "secret" not in serialized
    assert "private" not in serialized
    assert "REDACTED" in serialized


def test_receipt_removes_url_userinfo_and_fragment():
    receipt = build_receipt(
        run_id="run-123",
        tool_name="media-inspect",
        tool_version="1.0",
        status="failed",
        exit_code=1,
        input_metadata=[{"url": "https://alice:password@example.test/file?token=secret#private-fragment"}],
        output_artifacts=[],
        provenance={},
    )

    serialized = json.dumps(receipt.to_dict())
    assert "alice" not in serialized
    assert "password" not in serialized
    assert "secret" not in serialized
    assert "private-fragment" not in serialized
    assert "example.test/file" in serialized

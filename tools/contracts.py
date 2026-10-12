"""Versioned execution receipts with artifact hashes and sanitized provenance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import hashlib

SCHEMA_VERSION = "fyah-re/execution-receipt@1"
VALID_STATUSES = frozenset({"success", "failed", "blocked"})


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    if isinstance(value, str) and "://" in value:
        try:
            parts = urlsplit(value)
            if parts.scheme in {"http", "https"} and parts.netloc:
                query = urlencode([(k, "REDACTED") for k, _ in parse_qsl(parts.query, keep_blank_values=True)])
                return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))
        except ValueError:
            return "[REDACTED_URL]"
    return value


def artifact_metadata(path: str | Path, *, root: str | Path) -> dict[str, Any]:
    artifact, base = Path(path).resolve(), Path(root).resolve()
    try:
        relative = artifact.relative_to(base)
    except ValueError as exc:
        raise ValueError("artifact must be inside the declared root") from exc
    if not artifact.is_file():
        raise ValueError("artifact must be an existing regular file")
    digest = hashlib.sha256()
    with artifact.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": relative.as_posix(), "size_bytes": artifact.stat().st_size, "sha256": digest.hexdigest()}


@dataclass(frozen=True)
class ExecutionReceipt:
    schema_version: str
    run_id: str
    started_at: str
    ended_at: str
    tool_name: str
    tool_version: str
    input_metadata: list[dict[str, Any]]
    output_artifacts: list[dict[str, Any]]
    status: str
    exit_code: int
    duration_ms: int
    error_category: str | None
    provenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return _sanitize(asdict(self))


def build_receipt(*, run_id: str, tool_name: str, tool_version: str, status: str, exit_code: int,
                  input_metadata: list[dict[str, Any]], output_artifacts: list[dict[str, Any]],
                  provenance: dict[str, Any], started_at: datetime | None = None,
                  ended_at: datetime | None = None, error_category: str | None = None) -> ExecutionReceipt:
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid status: {status}")
    if not all(isinstance(v, str) and v.strip() for v in (run_id, tool_name, tool_version)):
        raise ValueError("run_id, tool_name and tool_version must be non-empty")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise ValueError("exit_code must be an integer")
    if (status == "success" and exit_code != 0) or (status != "success" and exit_code == 0):
        raise ValueError("exit_code must agree with status")
    end = ended_at or datetime.now(timezone.utc)
    start = started_at or end
    started, ended = _timestamp(start), _timestamp(end)
    duration_ms = int((end.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds() * 1000)
    if duration_ms < 0:
        raise ValueError("ended_at must not precede started_at")
    return ExecutionReceipt(
        schema_version=SCHEMA_VERSION, run_id=run_id, started_at=started, ended_at=ended,
        tool_name=tool_name, tool_version=tool_version, input_metadata=_sanitize(input_metadata),
        output_artifacts=_sanitize(output_artifacts), status=status, exit_code=exit_code,
        duration_ms=duration_ms, error_category=error_category, provenance=_sanitize(provenance),
    )


from pathlib import Path

import pytest

from tools import __main__ as cli


class FakeResponse:
    def __init__(self, payload: bytes, declared_size: int | None = None):
        self.payload = payload
        self.headers = {}
        if declared_size is not None:
            self.headers["Content-Length"] = str(declared_size)
        self.offset = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            result = self.payload[self.offset:]
            self.offset = len(self.payload)
            return result
        result = self.payload[self.offset:self.offset + size]
        self.offset += len(result)
        return result


def test_download_rejects_stream_larger_than_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "MAX_DOWNLOAD_BYTES", 8, raising=False)
    monkeypatch.setattr(cli.urllib.request, "urlopen", lambda *a, **k: FakeResponse(b"0123456789", 5))
    destination = tmp_path / "oversized.bin"

    with pytest.raises(ValueError, match="size limit"):
        cli.download("https://example.test/large.bin", destination)

    assert not destination.exists()


def test_download_streams_allowed_payload_to_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "MAX_DOWNLOAD_BYTES", 8, raising=False)
    monkeypatch.setattr(cli.urllib.request, "urlopen", lambda *a, **k: FakeResponse(b"12345678", 8))
    destination = tmp_path / "valid.bin"

    result = cli.download("https://example.test/valid.bin", destination)

    assert result == destination
    assert destination.read_bytes() == b"12345678"


def test_download_identifies_client_so_public_hosts_accept_it(tmp_path, monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=120):
        seen["user_agent"] = request.get_header("User-agent")
        seen["timeout"] = timeout
        return FakeResponse(b"ok", 2)

    monkeypatch.setattr(cli.urllib.request, "urlopen", fake_urlopen)
    destination = tmp_path / "identified.bin"

    cli.download(
        "https://upload.wikimedia.org/wikipedia/commons/4/40/Toreador_song_cleaned.ogg",
        destination,
    )

    user_agent = seen["user_agent"]
    assert user_agent.startswith("fyah-re/")
    assert "github.com/zenindiones-maker/fyah-reverse-engineering" in user_agent
    assert user_agent != "fyah-re-tools"
    assert destination.read_bytes() == b"ok"

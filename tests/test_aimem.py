"""AI Memory como harness mestre: testes sem servidor (zero-LLM, sem rede)."""
import json, os, pathlib, sys

import pytest


def test_record_tool_noop_without_session(monkeypatch):
    monkeypatch.delenv("AIMEM_SESSION_ID", raising=False)
    from aimem.hooks import record_tool
    assert record_tool("media-inspect", ["a.ogg"], "out/x.json", True, 0.1) is False


def test_record_tool_never_raises_when_server_down(monkeypatch):
    monkeypatch.setenv("AIMEM_SESSION_ID", "fyah-test")
    monkeypatch.setenv("AI_MEMORY_SERVER_URL", "http://127.0.0.1:9")
    from aimem.hooks import record_tool
    assert record_tool("media-inspect", ["a.ogg"], "out/x.json", True, 0.1) is False


def test_short_url_hides_query():
    from aimem.hooks import _short
    s = _short("https://example.com/a/b/file.ogg?sig=SECRET")
    assert "SECRET" not in s and s.endswith("file.ogg") and "example.com" in s


def test_ingest_key_stable_and_valid():
    from aimem.client import Client
    k1 = Client.ingest_key("a", "s", "post-tool-use", "1")
    assert k1 == Client.ingest_key("a", "s", "post-tool-use", "1")
    assert k1 != Client.ingest_key("a", "s", "post-tool-use", "2")
    assert len(k1) == 64 and all(c in "0123456789abcdef" for c in k1)


def test_redact_command():
    from aimem.__main__ import _redact
    r = _redact([sys.executable, "-m", "tools", "run", "x", "--input", "https://h.org/p/q.wav?t=1"])
    assert r.startswith("python -m tools run x") and "t=1" not in r


def test_session_degrades_without_server(tmp_path, monkeypatch):
    """Sem servidor o subordinado ainda roda (modo degradado) e a memória vai pro markdown."""
    import aimem.__main__ as m
    monkeypatch.setenv("AI_MEMORY_SERVER_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(m, "MEM", tmp_path / "memory")
    monkeypatch.chdir(tmp_path)
    rc = m.run_session("fyah-er", "teste", [sys.executable, "-c", "import os; assert os.environ['AIMEM_SESSION_ID']"],
                       next_steps=["seguir"])
    assert rc == 0
    ab = json.loads((tmp_path / "memory" / "handoffs" / "aberto.json").read_text())
    assert ab["from_agent"] == "fyah-er" and "seguir" in ab["next_steps"]
    assert list((tmp_path / "memory" / "sessoes").glob("*-teste-*.md"))


def test_workflows_route_through_aimemory():
    import yaml
    wf = pathlib.Path(__file__).resolve().parents[1] / ".github" / "workflows"
    for name in ("er-aimemory.yml", "er-analyze.yml", "er-harness.yml", "er-toolcheck.yml"):
        text = (wf / name).read_text()
        yaml.safe_load(text)
        assert "./.github/actions/setup-aimemory" in text, name
        assert "python -m aimem" in text, name
        assert "DEEPSEEK_API_KEY" not in text and "secrets." not in text, name

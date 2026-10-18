"""Gancho leve para ferramentas: registra cada execução na sessão AI Memory ativa.

No-op silencioso quando não há sessão (AIMEM_SESSION_ID) ou servidor — as
ferramentas continuam funcionando sozinhas, sem dependência dura.
"""
from __future__ import annotations

import json, os, time


def record_tool(name: str, inputs: list[str], out: str, ok: bool, elapsed: float, extra: dict | None = None) -> bool:
    sid = os.environ.get("AIMEM_SESSION_ID")
    if not sid:
        return False
    try:
        from aimem.client import Client
        c = Client(timeout=3)
        agent = os.environ.get("AIMEM_AGENT", "fyah-er")
        eid = f"{name}-{time.time_ns()}"
        resp = {"ok": ok, "elapsed_sec": round(elapsed, 2), "out": out, **(extra or {})}
        c.events(agent, sid, [("post-tool-use", eid, {
            "tool_name": f"fyah:{name}",
            "tool_input": {"command": f"python -m tools run {name}", "inputs": [_short(u) for u in inputs], "out": out},
            "tool_response": json.loads(json.dumps(resp, default=str))})])
        return True
    except Exception:  # noqa: BLE001
        return False


def _short(u: str) -> str:
    """Guarda só host + nome do arquivo (sem query string)."""
    if u.startswith(("http://", "https://")):
        from urllib.parse import urlsplit
        s = urlsplit(u)
        return f"{s.scheme}://{s.netloc}/…/{s.path.rsplit('/', 1)[-1]}"
    return os.path.basename(u)

"""Servidor falso (stdlib) com o contrato mínimo do ai-memory 3.1.1 usado pelo aimem.

Só para testes: /healthz, POST /mcp (tools/call), POST /hook/batch. Em session-end
grava a página de sessão "sem LLM" no data dir, como o servidor real faz.
"""
from __future__ import annotations

import json, pathlib, threading, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeAIMemory:
    def __init__(self, data_dir: pathlib.Path, *, reject_accept_by_id=False, nonjson=False, preload_open=()):
        self.data_dir = pathlib.Path(data_dir); self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reject_accept_by_id = reject_accept_by_id
        self.nonjson = nonjson
        self.handoffs: list[dict] = []
        for s in preload_open:
            self.handoffs.append({"id": uuid.uuid4().hex, "summary": s, "status": "open", "next_steps": [], "open_questions": []})
        self.prompts: dict[str, str] = {}
        self.calls: list[tuple] = []
        srv = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, obj=None, raw=None):
                body = raw if raw is not None else json.dumps(obj).encode()
                self.send_response(code); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

            def do_GET(self):
                if self.path == "/healthz":
                    return self._send(200, {"ok": True})
                self._send(404, {})

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                req = json.loads(self.rfile.read(n) or b"null")
                if srv.nonjson:
                    return self._send(401, raw=b"")
                if self.path == "/mcp":
                    p = req["params"]; name, args = p["name"], p.get("arguments", {})
                    srv.calls.append((name, args))
                    try:
                        res = srv.tool(name, args); err = False
                    except Exception as e:  # noqa: BLE001
                        res = str(e); err = True
                    text = res if isinstance(res, str) else json.dumps(res)
                    return self._send(200, {"jsonrpc": "2.0", "id": req.get("id"),
                                            "result": {"content": [{"type": "text", "text": text}], "isError": err}})
                if self.path == "/hook/batch":
                    out = []
                    for it in req:
                        q = it["url"]; b = it["body"]; sid = b.get("session_id")
                        if "event=user-prompt-submit" in q:
                            srv.prompts[sid] = b.get("prompt", "")
                        if "event=session-end" in q:
                            d = srv.data_dir / "wiki" / "w" / "p" / "sessions"; d.mkdir(parents=True, exist_ok=True)
                            (d / f"{uuid.uuid4().hex}.md").write_text(f"---\nagent: other\n---\n# {srv.prompts.get(sid, '')}\nM3, no-LLM heuristic\n")
                        out.append({"outcome": "stored"})
                    return self._send(200, {"results": out})
                self._send(404, {})

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tool(self, name, a):
        if name == "memory_write_page":
            return {"page_id": uuid.uuid4().hex}
        if name == "memory_query":
            return {"hits": []}
        if name == "memory_briefing":
            return "briefing falso"
        if name == "memory_handoff_begin":
            h = {"id": uuid.uuid4().hex, "summary": a.get("summary"), "status": "open",
                 "next_steps": a.get("next_steps", []), "open_questions": a.get("open_questions", [])}
            self.handoffs.append(h); return {"handoff_id": h["id"]}
        if name == "memory_handoff_accept":
            hid = a.get("handoff_id")
            if hid and self.reject_accept_by_id:
                raise RuntimeError("handoff_id not found")
            for h in self.handoffs:
                if h["status"] == "open" and (not hid or h["id"] == hid):
                    h["status"] = "claimed"; return {"status": "claimed", "handoff": h}
            return {"status": "none"}
        if name == "memory_handoff_list":
            return [h for h in self.handoffs if h["status"] == "open"]
        raise RuntimeError(f"tool desconhecida {name}")

    def close(self):
        self.httpd.shutdown()

"""Cliente mínimo (stdlib) do servidor ai-memory local — caminho zero-LLM.

Fala com o `ai-memory serve --transport http` em loopback:
  * MCP (`POST /mcp`): memory_write_page, memory_query, memory_briefing,
    memory_handoff_begin / accept / list.
  * Captura de ciclo de vida (`POST /hook/batch`): session-start,
    post-tool-use, session-end — o servidor resume a sessão SEM LLM
    ("M3, no-LLM heuristic").

O bearer é o arquivo aleatório que o próprio `ai-memory init` gera dentro do
data dir efêmero do runner. Não é chave de API, não tem cadastro, não sai da
máquina e morre com o job.
"""
from __future__ import annotations

import hashlib, json, os, pathlib, time, urllib.error, urllib.request

WORKSPACE = os.environ.get("AIMEM_WORKSPACE", "fyah")
PROJECT = os.environ.get("AIMEM_PROJECT", "fyah-reverse-engineering")
EXTENSION = "fyah.er"  # namespace do produtor externo (provenance)


def data_dir() -> pathlib.Path:
    d = os.environ.get("AI_MEMORY_DATA_DIR")
    if d:
        return pathlib.Path(d)
    return pathlib.Path.home() / ".local" / "share" / "ai-memory"


def server_url() -> str:
    return os.environ.get("AI_MEMORY_SERVER_URL", "http://127.0.0.1:49374").rstrip("/")


def _local_bearer() -> str | None:
    p = data_dir() / "auth-token"
    return p.read_text().strip() if p.is_file() else None


class AIMemoryError(RuntimeError):
    pass


class Client:
    def __init__(self, url: str | None = None, timeout: float = 30):
        self.url = url or server_url()
        self.timeout = timeout
        self._id = 0
        self.bearer = _local_bearer()

    # ---- transporte -------------------------------------------------
    def _post(self, path: str, body) -> tuple[int, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.bearer:
            h["Authorization"] = "Bearer " + self.bearer
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(), headers=h)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(errors="ignore")

    def healthy(self) -> bool:
        try:
            with urllib.request.urlopen(self.url + "/healthz", timeout=2) as r:
                return r.status == 200
        except Exception:  # noqa: BLE001
            return False

    def wait(self, timeout: float = 60) -> None:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.healthy():
                return
            time.sleep(0.5)
        raise AIMemoryError(f"ai-memory não respondeu em {self.url}")

    # ---- MCP --------------------------------------------------------
    def mcp(self, tool: str, **args):
        args.setdefault("workspace", WORKSPACE)
        args.setdefault("project", PROJECT)
        self._id += 1
        code, raw = self._post("/mcp", {"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                                        "params": {"name": tool, "arguments": args}})
        if raw.startswith("event:") or raw.startswith("data:"):
            raw = next(l[5:].strip() for l in raw.splitlines() if l.startswith("data:"))
        try:
            d = json.loads(raw)
        except json.JSONDecodeError as e:
            raise AIMemoryError(f"{tool}: resposta não-JSON (HTTP {code}): {raw[:200]!r}") from e
        if d.get("error"):
            raise AIMemoryError(f"{tool}: {d['error']}")
        res = d.get("result") or {}
        text = "".join(c.get("text", "") for c in res.get("content", []))
        if res.get("isError"):
            raise AIMemoryError(f"{tool}: {text[:500]}")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    # ---- captura de ciclo de vida ----------------------------------
    @staticmethod
    def ingest_key(*parts: str) -> str:
        ident = json.dumps(["external-capture-v1", EXTENSION, *parts])
        return hashlib.sha256(ident.encode()).hexdigest()

    def events(self, agent: str, session_id: str, items: list[tuple[str, str, dict]]) -> dict:
        """items = [(event, event_id, body_extra)]; ordem preservada."""
        batch = []
        for event, eid, extra in items:
            q = (f"event={event}&agent={agent}&workspace={WORKSPACE}&project={PROJECT}"
                 f"&extension={EXTENSION}&source_event={event}"
                 f"&ingest_key={self.ingest_key(agent, session_id, event, eid)}")
            body = {"session_id": session_id, "cwd": os.getcwd(), **extra}
            batch.append({"url": "/hook?" + q, "body": body})
        code, raw = self._post("/hook/batch", batch)
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            d = {"raw": raw[:500]}
        d["http"] = code
        return d

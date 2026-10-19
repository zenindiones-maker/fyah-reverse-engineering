"""Infra de teste: remoto bare + clones independentes = "jobs" do Actions."""
from __future__ import annotations

import json, os, pathlib, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve()


def _repo_toplevel(start: pathlib.Path) -> pathlib.Path:
    """Raiz do checkout git que contém `start` (arquivo ou dir)."""
    cwd = start if start.is_dir() else start.parent
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd, capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git toplevel ausente a partir de {start}: {(r.stderr or '').strip()}")
    return pathlib.Path(r.stdout.strip())


# Código sob teste e histórico: raiz do checkout (descoberta via git), override opcional por env.
# Sem caminhos absolutos de máquina.
CODE = pathlib.Path(os.environ["FYAH_CODE_DIR"]) if os.environ.get("FYAH_CODE_DIR") else _repo_toplevel(HERE)
HIST = pathlib.Path(os.environ["FYAH_HISTORY_REPO"]) if os.environ.get("FYAH_HISTORY_REPO") else _repo_toplevel(HERE)
PY = sys.executable
DEAD = "http://127.0.0.1:9"


def git(cwd, *a, check=True, **kw):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, **kw)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(a)}: {r.stderr}")
    return r.stdout.strip()


def overlay_code(dst: pathlib.Path):
    """Copia o código sob teste (aimem/ + scripts/aimem_commit.sh) para o repo do teste."""
    if (dst / "aimem").exists():
        shutil.rmtree(dst / "aimem")
    shutil.copytree(CODE / "aimem", dst / "aimem", ignore=shutil.ignore_patterns("__pycache__"))
    (dst / "scripts").mkdir(exist_ok=True)
    shutil.copy2(CODE / "scripts" / "aimem_commit.sh", dst / "scripts" / "aimem_commit.sh")


def make_remote(tmp: pathlib.Path, *, memory_from: pathlib.Path | None = None) -> pathlib.Path:
    """Remoto bare com: código sob teste + docs/memory (do checkout sob teste por padrão)."""
    tmp = pathlib.Path(tmp); tmp.mkdir(parents=True, exist_ok=True)
    remote = tmp / "origin.git"
    git(tmp, "init", "-q", "--bare", "-b", "main", str(remote))
    seed = tmp / "seed"
    git(tmp, "clone", "-q", str(remote), str(seed))
    _ident(seed)
    overlay_code(seed)
    (seed / "docs").mkdir()
    src_mem = memory_from or (HIST / "docs" / "memory")
    if not src_mem.is_dir():
        raise RuntimeError(f"docs/memory ausente em HIST={HIST} (src={src_mem})")
    shutil.copytree(src_mem, seed / "docs" / "memory")
    (seed / "README.md").write_text("base\n")
    (seed / "docs" / "ferramentas").mkdir(parents=True)
    (seed / "docs" / "ferramentas" / "STATUS.md").write_text("status base\n")
    (seed / ".gitignore").write_text("out/\n__pycache__/\n")
    git(seed, "add", "-A"); git(seed, "commit", "-qm", "base"); git(seed, "push", "-q", "origin", "HEAD:main")
    return remote


def _ident(repo):
    git(repo, "config", "user.name", "teste"); git(repo, "config", "user.email", "t@x")


class Job:
    """Um job do Actions: checkout próprio, data dir próprio, servidor próprio (ou nenhum)."""

    def __init__(self, tmp, remote, name, *, run_id, attempt=1, server=None, workflow=None, extra_env=None):
        self.dir = tmp / f"job-{name}-{run_id}-{attempt}"
        git(tmp, "clone", "-q", str(remote), str(self.dir)); _ident(self.dir)
        self.name, self.server = name, server
        self.env = dict(os.environ)
        for k in list(self.env):
            if k.startswith(("GITHUB_", "AIMEM_", "AI_MEMORY_")):
                self.env.pop(k)
        self.env.update({
            "AI_MEMORY_DATA_DIR": str(server.data_dir if server else tmp / f"data-{name}-{run_id}-{attempt}"),
            "AI_MEMORY_SERVER_URL": server.url if server else DEAD,
            "GITHUB_RUN_ID": str(run_id), "GITHUB_RUN_ATTEMPT": str(attempt),
            "GITHUB_WORKFLOW": workflow or name, "GITHUB_SHA": git(self.dir, "rev-parse", "HEAD"),
            "AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1",
            **(extra_env or {}),
        })
        pathlib.Path(self.env["AI_MEMORY_DATA_DIR"]).mkdir(parents=True, exist_ok=True)

    def run(self, *args, timeout=120):
        return subprocess.run(list(args), cwd=self.dir, env=self.env, capture_output=True, text=True, timeout=timeout)

    def seed(self):
        if self.server:
            return self.run(PY, "-m", "aimem", "seed")

    def session(self, *cmd, label=None, nxt=None):
        label = label or f"job-{self.name}"
        a = [PY, "-m", "aimem", "session", "--agent", f"ag-{self.name}", "--label", label]
        for n in nxt or []:
            a += ["--next", n]
        r = self.run(*a, "--", *(cmd or ("true",)))
        self.last = r
        return r

    def received(self):
        p = self.dir / "out" / "aimem" / f"session-ag-{self.name.lower()}.json"
        if not p.is_file():
            return "<sessão não gravou registro>"
        return json.loads(p.read_text()).get("handoff_received")

    def commit(self, *msg):
        return self.run("bash", "scripts/aimem_commit.sh", *(msg or (self.name,)), timeout=300)


def remote_file(tmp, remote, path, ref="main"):
    chk = tmp / "verif"
    if chk.exists():
        shutil.rmtree(chk)
    git(tmp, "clone", "-q", str(remote), str(chk))
    p = chk / path
    return p.read_bytes() if p.exists() else None


def remote_tree(tmp, remote) -> pathlib.Path:
    tmp = pathlib.Path(tmp); tmp.mkdir(parents=True, exist_ok=True)
    chk = tmp / "verif"
    if chk.exists():
        shutil.rmtree(chk)
    git(tmp, "clone", "-q", str(remote), str(chk))
    return chk


def fila(job_or_dir) -> list[dict]:
    """Lista a fila via CLI pública (`python -m aimem fila --json`)."""
    j = job_or_dir
    r = j.run(PY, "-m", "aimem", "fila", "--json")
    assert r.returncode == 0, f"`python -m aimem fila --json` indisponível/falhou: {r.stderr[-300:]}"
    return json.loads(r.stdout)

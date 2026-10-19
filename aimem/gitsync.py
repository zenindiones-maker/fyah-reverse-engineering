"""Commit/push da memória com CAS, merge semântico e artefato de conflito.

Nunca usa `-X theirs`. Em falha irrecuperável: salva patch+bundle em
out/aimem/conflito/, imprime ::error:: e sai com código != 0.
"""
from __future__ import annotations

import json, os, pathlib, random, shutil, subprocess, time

from aimem import ledger

ALLOWED_DEFAULT = ("docs/memory/",)
CONFLICT_DIR = pathlib.Path("out/aimem/conflito")


def _sync_ref() -> str:
    """Branch-alvo do push/rebase. Em Actions: GITHUB_REF_NAME; override: AIMEM_SYNC_REF; senão main."""
    return (os.environ.get("AIMEM_SYNC_REF") or os.environ.get("GITHUB_REF_NAME") or "main").strip() or "main"



class SyncError(RuntimeError):
    pass


def _run(cmd, *, check=True, cwd=None, env=None):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if check and r.returncode:
        raise SyncError(f"{' '.join(cmd)}: {(r.stderr or r.stdout)[-500:]}")
    return r


def _backoff(i: int) -> None:
    base = float(os.environ.get("AIMEM_SYNC_BACKOFF", "1"))
    if base <= 0:
        return
    time.sleep(base * (2 ** (i - 1)) + random.uniform(0, base))


def _allowed() -> list[str]:
    extra = [x for x in (os.environ.get("AIMEM_SYNC_EXTRA") or "").split(":") if x]
    return list(ALLOWED_DEFAULT) + extra


def _stage_allowed() -> list[str]:
    """Só paths autorizados. Rejeita alterações em paginas/ (curadoria humana)."""
    r = _run(["git", "status", "--porcelain", "-uall"], check=False)
    staged = []
    for line in (r.stdout or "").splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if not any(path == a.rstrip("/") or path.startswith(a) for a in _allowed()):
            continue
        if path.startswith("docs/memory/paginas/"):
            continue
        staged.append(path)
    if staged:
        _run(["git", "add", "--", *staged])
    return staged



def _secret_patterns():
    """Padrões que nunca podem aparecer em artefato de conflito/recuperação."""
    import re
    return [
        re.compile(r"ghp_[A-Za-z0-9]{20,}"),
        re.compile(r"gho_[A-Za-z0-9]{20,}"),
        re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----"),
        re.compile(r"(?i)ai[-_]?memory[^\n]{0,40}(token|secret|password)\s*[=:]\s*\S+"),
        re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    ]


_FORBIDDEN_NAMES = {
    "config.toml", ".env", ".env.local", "credentials", "credentials.json",
    "id_rsa", "id_ed25519", ".netrc",
}
_FORBIDDEN_SUFFIXES = (
    ".db", ".sqlite", ".sqlite3", ".redb", ".duckdb", ".mdb",
    ".pem", ".p12", ".pfx", ".key",
)


class ArtifactSecretError(SyncError):
    """Artefato de conflito contém segredo ou arquivo proibido."""


def scan_artifact(dest: pathlib.Path) -> None:
    """Varre o diretório do artefato; levanta ArtifactSecretError se achar segredo/arquivo proibido."""
    dest = pathlib.Path(dest)
    hits = []
    for f in dest.rglob("*"):
        if not f.is_file():
            continue
        name = f.name.lower()
        if name in _FORBIDDEN_NAMES or any(name.endswith(s) for s in _FORBIDDEN_SUFFIXES):
            hits.append(f"arquivo_proibido:{f.relative_to(dest)}")
            continue
        if f.suffix == ".bundle" or name.endswith(".bundle"):
            # descompacta em tmp e varre blobs de docs/memory
            tmp = dest / f".bundle-scan-{f.name}"
            if tmp.exists():
                shutil.rmtree(tmp)
            tmp.mkdir()
            r = _run(["git", "clone", "-q", str(f), str(tmp / "repo")], check=False)
            text = (r.stdout or "") + (r.stderr or "")
            if r.returncode == 0:
                repo = tmp / "repo"
                for blob in repo.rglob("*"):
                    if not blob.is_file() or ".git" in blob.parts:
                        continue
                    try:
                        text += "\n" + blob.read_text(errors="replace")
                    except Exception:
                        pass
                shutil.rmtree(tmp, ignore_errors=True)
            else:
                text += _run(["git", "bundle", "list-heads", str(f)], check=False).stdout or ""
        else:
            try:
                text = f.read_text(errors="replace")
            except Exception:
                text = f.read_bytes()[:200_000].decode("utf-8", errors="replace")
        for pat in _secret_patterns():
            if pat.search(text):
                hits.append(f"padrao:{pat.pattern[:40]}:{f.relative_to(dest)}")
                break
    if hits:
        raise ArtifactSecretError("artefato bloqueado: " + "; ".join(hits[:8]))


def _preserve(reason: str) -> pathlib.Path:
    """Salva patch+bundle só de docs/memory (commits locais à frente do remoto). Varre segredos."""
    CONFLICT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dest = CONFLICT_DIR / f"{stamp}-{os.getpid()}-{time.time_ns()}"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "reason.txt").write_text(reason + "\n")
    ref = _sync_ref()
    remote_ref = f"origin/{ref}"
    allow = _allowed()
    ahead = _run(["git", "rev-list", "--count", f"{remote_ref}..HEAD"], check=False)
    n_ahead = int((ahead.stdout or "0").strip() or "0") if ahead.returncode == 0 else 0
    if n_ahead > 0:
        _run(["git", "format-patch", f"{remote_ref}..HEAD", "-o", str(dest), "--", *allow], check=False)
    if not list(dest.glob("*.patch")):
        d = _run(["git", "diff", "HEAD", "--", *allow], check=False)
        if d.stdout:
            (dest / "working-tree.patch").write_text(d.stdout)
    bundle = dest / "memoria.bundle"
    mem_shas = _run(
        ["git", "rev-list", "--reverse", f"{remote_ref}..HEAD", "--", *allow],
        check=False,
    )
    shas = [x for x in (mem_shas.stdout or "").split() if x]
    if shas:
        tmp_ref = f"refs/tags/aimem-art-{os.getpid()}-{time.time_ns()}"
        _run(["git", "update-ref", tmp_ref, shas[-1]], check=False)
        try:
            r = _run(["git", "bundle", "create", str(bundle), f"{remote_ref}..{tmp_ref}"], check=False)
            if r.returncode != 0:
                (dest / "NO_BUNDLE.txt").write_text(f"bundle falhou: {(r.stderr or '')[-300:]}\n")
        finally:
            _run(["git", "update-ref", "-d", tmp_ref], check=False)
    elif list(dest.glob("*.patch")):
        (dest / "NO_BUNDLE.txt").write_text(
            "sem commits allowlist à frente do remoto; só patch do working tree\n"
        )
    br = f"aimem-conflito-{stamp}"
    (dest / "README.md").write_text(
        f"# Conflito de memória\n\n{reason}\n\n"
        f"Escopo: allowlist {allow}. Bundle = commits que tocam a allowlist em `{remote_ref}..`.\n\n"
        f"Recuperação: `git fetch {bundle.name} HEAD:{br}` (se bundle existir) e inspecione o patch.\n"
    )
    try:
        scan_artifact(dest)
    except ArtifactSecretError as e:
        (dest / "BLOCKED.txt").write_text(str(e) + "\n")
        for f in list(dest.iterdir()):
            if f.name in ("reason.txt", "BLOCKED.txt", "README.md"):
                continue
            if f.is_file():
                f.unlink()
            elif f.is_dir():
                shutil.rmtree(f)
        raise
    return dest


def _semantic_rebase() -> None:
    """Durante rebase com conflitos: merge semântico de fila/*.json; resto = abort."""
    unmerged = _run(["git", "diff", "--name-only", "--diff-filter=U"], check=False).stdout.split()
    if not unmerged:
        return
    for path in unmerged:
        if not path.startswith("docs/memory/handoffs/fila/") or not path.endswith(".json"):
            _run(["git", "rebase", "--abort"], check=False)
            raise SyncError(f"conflito em {path}: não é fila de handoff")
        ours = pathlib.Path(path)
        # ours = working tree (local); theirs = do remoto (durante rebase: stage 3 = theirs = upstream)
        base = _run(["git", "show", f":2:{path}"], check=False)  # ours (local being replayed)
        th = _run(["git", "show", f":3:{path}"], check=False)    # theirs (onto)
        if base.returncode or th.returncode:
            _run(["git", "rebase", "--abort"], check=False)
            raise SyncError(f"não consegui ler estágios de {path}")
        try:
            merged = ledger.merge_items(json.loads(base.stdout), json.loads(th.stdout))
        except ledger.UnsafeMerge as e:
            _run(["git", "rebase", "--abort"], check=False)
            dest = _preserve(f"UnsafeMerge em {path}: {e}")
            raise SyncError(f"UnsafeMerge em {path}: {e} (artefato {dest})")
        ours.write_text(ledger.dumps(merged))
        _run(["git", "add", "--", path])
    r = _run(["git", "rebase", "--continue"], check=False, env={**os.environ, "GIT_EDITOR": "true"})
    if r.returncode:
        _run(["git", "rebase", "--abort"], check=False)
        raise SyncError(f"rebase --continue falhou: {r.stderr[-300:]}")


def push_paths(msg: str, *, max_tries: int = 5) -> str:
    """Stage allowlist → commit se houver mudança → push com retry + merge semântico.
    Retorna 'noop' | 'pushed'. Em falha: preserva artefato e levanta SyncError.
    Alvo: AIMEM_SYNC_REF ou GITHUB_REF_NAME ou main (não force-push em outra branch).
    """
    ref = _sync_ref()
    remote_ref = f"origin/{ref}"
    _run(["git", "config", "user.name", "github-actions[bot]"], check=False)
    _run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=False)
    staged = _stage_allowed()
    made_commit = False
    if staged and _run(["git", "diff", "--cached", "--quiet"], check=False).returncode != 0:
        _run(["git", "commit", "-q", "-m", msg]); made_commit = True
    # também empurra commits locais já existentes (HEAD à frente do remoto)
    ahead = _run(["git", "rev-list", "--count", f"{remote_ref}..HEAD"], check=False)
    n_ahead = int((ahead.stdout or "0").strip() or "0") if ahead.returncode == 0 else (1 if made_commit else 0)
    if ahead.returncode != 0:
        _run(["git", "fetch", "origin", ref], check=False)
        ahead = _run(["git", "rev-list", "--count", f"{remote_ref}..HEAD"], check=False)
        n_ahead = int((ahead.stdout or "0").strip() or "0") if ahead.returncode == 0 else (1 if made_commit else 0)
    if not made_commit and n_ahead == 0:
        print("Memória sem mudanças"); return "noop"
    last_err = ""
    for i in range(1, max_tries + 1):
        r = _run(["git", "push", "origin", f"HEAD:{ref}"], check=False)
        if r.returncode == 0:
            print("memória salva"); return "pushed"
        last_err = (r.stderr or r.stdout)[-400:]
        _run(["git", "fetch", "origin", ref], check=False)
        rb = _run(["git", "rebase", remote_ref], check=False)
        if rb.returncode == 0:
            continue
        try:
            _semantic_rebase()
        except SyncError as e:
            dest = _preserve(str(e))
            print(f"::error::não consegui salvar docs/memory: {e}. Artefato em {dest}", flush=True)
            raise
        _backoff(i)
    dest = _preserve(f"push recusado após {max_tries} tentativas: {last_err}")
    print(f"::error::não consegui salvar docs/memory (push falhou). Artefato em {dest}", flush=True)
    raise SyncError(last_err)


def cas_update(path: pathlib.Path, mutate, *, msg: str, max_tries: int = 8):
    """Compare-and-swap de um arquivo: mutate(item) → save → push; em conflito refetch e tenta de novo.
    Após push, refetch e valida o estado remoto via `verify` (mutate deve deixar token no item).
    Retorna o item remoto validado.
    """
    last = None
    for i in range(1, max_tries + 1):
        _run(["git", "fetch", "origin", _sync_ref()], check=False)
        # alinhar working tree do arquivo com o remoto
        _run(["git", "checkout", f"origin/{_sync_ref()}", "--", str(path)], check=False)
        if not path.is_file():
            raise SyncError(f"{path} sumiu no remoto")
        item = json.loads(path.read_text())
        try:
            item = mutate(item)
        except ledger.LostClaim:
            raise
        except ledger.LedgerError:
            raise
        path.write_text(ledger.dumps(item))
        token = (item.get("consumer") or {}).get("claim_token")
        try:
            push_paths(msg)
        except SyncError as e:
            marker = os.environ.get("AIMEM_PUSH_REJECT_LOG")
            if marker:
                pathlib.Path(marker).write_text(f"rejected:{e}\n")
            _backoff(i); last = "push"; continue
        # gancho de teste: permite simular um escritor intruso entre push e validação
        hook = os.environ.get("AIMEM_TEST_AFTER_CLAIM_PUSH")
        if hook:
            subprocess.run(hook, shell=True, check=False)
        # validação remota
        _run(["git", "fetch", "origin", _sync_ref()], check=False)
        _run(["git", "checkout", f"origin/{_sync_ref()}", "--", str(path)], check=False)
        remote = json.loads(path.read_text())
        if token:
            if remote.get("state") == "claimed":
                ledger.verify_mine(remote, token)  # LostClaim propaga
            else:
                # consumed / pending / failed: a última transição tem de ser nossa
                last = (remote.get("history") or [{}])[-1]
                me = ledger.me()["consumer_id"]
                if last.get("claim_token") != token and last.get("by") != me:
                    last = "stolen"; _backoff(i); continue
        if remote.get("state") != item.get("state"):
            last = "state-mismatch"; _backoff(i); continue
        return remote
    raise SyncError(f"CAS esgotou tentativas ({last})")


def claim_one(mem: pathlib.Path) -> dict | None:
    """Tenta claim do primeiro item claimable; CAS + validação remota. None se a fila está vazia/ocupada."""
    for _ in range(8):
        cands = ledger.claimable(mem)
        if not cands:
            # refetch e tenta de novo uma vez (outro job pode ter liberado)
            _run(["git", "fetch", "origin", _sync_ref()], check=False)
            _run(["git", "checkout", f"origin/{_sync_ref()}", "--", "docs/memory/handoffs/fila"], check=False)
            cands = ledger.claimable(mem)
        if not cands:
            return None
        item, why = cands[0]
        path = ledger.fila_dir(mem) / f"{item['id']}.json"
        token_box = {}

        def mut(it, _why=why, _box=token_box):
            # revalida claimability no estado fresco
            ok, reason = False, ""
            m = ledger.me()
            if it["state"] == "pending":
                ok, reason = True, _why
            elif it["state"] == "claimed":
                c = it.get("consumer") or {}
                if c.get("consumer_id") == m["consumer_id"]:
                    ok, reason = True, "retry (mesmo run)"
                elif ledger._expired(it):
                    ok, reason = True, "lease expirado"
            if not ok:
                raise ledger.LostClaim(f"{it['id']} não é claimable")
            out = ledger.apply_claim(it, reason)
            _box["token"] = out["consumer"]["claim_token"]
            return out

        try:
            return cas_update(path, mut, msg=f"memoria: claim {item['id'][:40]}")
        except ledger.LostClaim:
            continue
        except SyncError:
            continue
    return None


def confirm(mem: pathlib.Path, iid: str, *, ok: bool) -> dict:
    path = ledger.fila_dir(mem) / f"{iid}.json"

    def mut(it):
        ledger.verify_mine(it, (it.get("consumer") or {}).get("claim_token") or "")
        if ok:
            return ledger.apply_consume(it, "success")
        return ledger.apply_release(it, "falha do consumidor (rc!=0)")

    return cas_update(path, mut, msg=f"memoria: {'consumed' if ok else 'release'} {iid[:40]}")



def claim_id(mem: pathlib.Path, iid: str) -> dict:
    """Claim de um handoff específico (CAS + validação remota). LostClaim se outro dono."""
    path = ledger.fila_dir(mem) / f"{iid}.json"
    if not path.is_file():
        _run(["git", "fetch", "origin", _sync_ref()], check=False)
        _run(["git", "checkout", f"origin/{_sync_ref()}", "--", str(path)], check=False)
    if not path.is_file():
        raise SyncError(f"handoff {iid} ausente")

    def mut(it):
        m = ledger.me()
        ok, reason = False, ""
        if it["state"] == "pending":
            ok, reason = True, "claim"
        elif it["state"] == "claimed":
            c = it.get("consumer") or {}
            if c.get("consumer_id") == m["consumer_id"]:
                ok, reason = True, "retry (mesmo run)"
            elif ledger._expired(it):
                ok, reason = True, "lease expirado"
        if not ok:
            raise ledger.LostClaim(f"{it['id']} não é claimable (state={it['state']})")
        return ledger.apply_claim(it, reason)

    return cas_update(path, mut, msg=f"memoria: claim {iid[:40]}")

"""Regressão: destino do push da memória é fail-closed.

- AIMEM_FORBID_MAIN=1 bloqueia main (inclusive variações de grafia/refspec).
- Sem fallback implícito para main: ref ausente, inconsistente, inválido, ou Actions sem
  GITHUB_REF_NAME → falha explícita ANTES de qualquer `git push`.
- Destinos válidos (branch via GITHUB_REF_NAME / AIMEM_SYNC_REF, main via GITHUB_REF_NAME=main
  sem FORBID_MAIN) continuam funcionando com o refspec exato.

Um wrapper `git` no PATH do subprocesso registra cada invocação: prova que `push` não foi
executado (não basta o remoto ficar inalterado). Tudo em tmp_path + remoto bare.
"""
from __future__ import annotations

import os, pathlib, shutil, stat, subprocess

import pytest

from tests.p0a.helpers import PY, git, make_remote

BRANCH = "p0a-fila-handoffs"
REAL_GIT = shutil.which("git")


def _refs(remote) -> dict:
    out = git(remote, "show-ref")
    return {l.split()[1]: l.split()[0] for l in out.splitlines() if l.strip()}


def _setup(tmp_path):
    remote = make_remote(tmp_path)
    seed = tmp_path / "brseed"
    git(tmp_path, "clone", "-q", str(remote), str(seed))
    git(seed, "checkout", "-qb", BRANCH)
    git(seed, "push", "-q", "origin", f"HEAD:{BRANCH}")
    w = tmp_path / "w"
    git(tmp_path, "clone", "-q", "-b", BRANCH, str(remote), str(w))
    git(w, "config", "user.name", "t"); git(w, "config", "user.email", "t@x")
    # commit local pré-existente + mudança não commitada em docs/memory
    (w / "docs/memory/sessoes").mkdir(parents=True, exist_ok=True)
    (w / "docs/memory/sessoes/local-commit.md").write_text("commit local\n")
    git(w, "add", "docs/memory/sessoes/local-commit.md"); git(w, "commit", "-qm", "mem local")
    (w / "docs/memory/sessoes/nao-commitado.md").write_text("dado não commitado\n")
    return remote, w


def _wrapper(tmp_path) -> tuple[pathlib.Path, pathlib.Path]:
    bindir = tmp_path / "gitwrap"; bindir.mkdir(exist_ok=True)
    log = tmp_path / "git-calls.log"
    w = bindir / "git"
    w.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{log}"\nexec "{REAL_GIT}" "$@"\n')
    w.chmod(w.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bindir, log


def _env(tmp_path, **kv):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("GITHUB_", "AIMEM_", "AI_MEMORY_"))}
    bindir, _ = _wrapper(tmp_path)
    e.update({"AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1",
              "GITHUB_WORKFLOW": "t", "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1",
              "AI_MEMORY_DATA_DIR": str(tmp_path / "d"),
              # wrapper git primeiro; aimem_commit.sh chama `python3` → mesmo interpretador do teste
              "PATH": os.pathsep.join([str(bindir), str(pathlib.Path(PY).parent), os.environ.get("PATH", "")])})
    e.update(kv)
    return e


def _pushes(tmp_path) -> list[str]:
    log = tmp_path / "git-calls.log"
    if not log.is_file():
        return []
    return [l for l in log.read_text().splitlines() if "push" in l.split()]


def _sync(w, env, via):
    (pathlib.Path(env["AI_MEMORY_DATA_DIR"]).parent / "git-calls.log").unlink(missing_ok=True)
    cmd = [PY, "-m", "aimem", "sync", "--msg", "t"] if via == "cli" else ["bash", "scripts/aimem_commit.sh", "t"]
    return subprocess.run(cmd, cwd=w, env=env, capture_output=True, text=True, timeout=120)


def _assert_bloqueado(tmp_path, env, frase, vias=("cli", "script")):
    remote, w = _setup(tmp_path)
    before = _refs(remote)
    local_head = git(w, "rev-parse", "HEAD")
    for via in vias:
        r = _sync(w, env, via)
        out = r.stdout + r.stderr
        assert r.returncode != 0, f"[{via}] {out}"
        assert frase in out, f"[{via}] {out}"
        assert _pushes(tmp_path) == [], f"[{via}] git push executado: {_pushes(tmp_path)}"
        assert _refs(remote) == before, f"[{via}] remoto alterado: {_refs(remote)}"
        assert git(w, "rev-parse", "HEAD") == local_head  # commit local preservado
        assert git(w, "cat-file", "-t", local_head) == "commit"
        assert (w / "docs/memory/sessoes/nao-commitado.md").read_text() == "dado não commitado\n"


def _assert_push_ok(tmp_path, env, dest, via="cli"):
    remote, w = _setup(tmp_path)
    before = _refs(remote)
    if dest == "main":
        # trabalho em main (workflows de main): clone de main com commit local
        w2 = tmp_path / "wm"; git(tmp_path, "clone", "-q", str(remote), str(w2))
        git(w2, "config", "user.name", "t"); git(w2, "config", "user.email", "t@x")
        (w2 / "docs/memory/sessoes").mkdir(parents=True, exist_ok=True)
        (w2 / "docs/memory/sessoes/em-main.md").write_text("main\n")
        w = w2
    r = _sync(w, env, via)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _pushes(tmp_path) == [f"push origin HEAD:refs/heads/{dest}"], _pushes(tmp_path)
    after = _refs(remote)
    assert after[f"refs/heads/{dest}"] == git(w, "rev-parse", "HEAD")
    assert after[f"refs/heads/{dest}"] != before[f"refs/heads/{dest}"]
    other = "main" if dest != "main" else BRANCH
    assert after[f"refs/heads/{other}"] == before[f"refs/heads/{other}"]
    assert set(after) == set(before)


# ---------------- FORBID_MAIN ----------------

@pytest.mark.parametrize("var", ["GITHUB_REF_NAME", "AIMEM_SYNC_REF"])
def test_forbid_main_bloqueia_sem_push_e_preserva_dados(tmp_path, var):
    env = _env(tmp_path, AIMEM_FORBID_MAIN="1", GITHUB_REF_NAME="main")
    if var == "AIMEM_SYNC_REF":
        env["AIMEM_SYNC_REF"] = "main"
    _assert_bloqueado(tmp_path, env, "push para main proibido")


@pytest.mark.parametrize("ref", ["refs/heads/main", " main", "main ", "MAIN", "Main",
                                 "refs/heads/MAIN", "+main", "HEAD:main", "+refs/heads/main"])
def test_forbid_main_variacoes_bloqueadas(tmp_path, ref):
    env = _env(tmp_path, AIMEM_FORBID_MAIN="1", AIMEM_SYNC_REF=ref, GITHUB_REF_NAME=ref)
    _assert_bloqueado(tmp_path, env, "push para main proibido", vias=("cli",))


# ---------------- destino indeterminado / inconsistente / inválido ----------------

def test_sem_ref_definido_falha_sem_fallback_main(tmp_path):
    _assert_bloqueado(tmp_path, _env(tmp_path), "destino do push indeterminado")


def test_refs_inconsistentes_falham(tmp_path):
    env = _env(tmp_path, AIMEM_SYNC_REF=BRANCH, GITHUB_REF_NAME="outra-branch")
    _assert_bloqueado(tmp_path, env, "inconsistente")


@pytest.mark.parametrize("ref", ["", "   ", "a b", "foo..bar", "x~1", "x:y", "+x",
                                 "refs/heads/x", "-x", "x.lock"])
def test_ref_invalido_falha(tmp_path, ref):
    _assert_bloqueado(tmp_path, _env(tmp_path, AIMEM_SYNC_REF=ref), "ref inválido", vias=("cli",))


@pytest.mark.parametrize("com_sync_ref", [False, True])
def test_github_actions_sem_github_ref_name_falha(tmp_path, com_sync_ref):
    extra = {"GITHUB_ACTIONS": "true"}
    if com_sync_ref:
        extra["AIMEM_SYNC_REF"] = BRANCH
    _assert_bloqueado(tmp_path, _env(tmp_path, **extra), "GITHUB_REF_NAME ausente")


# ---------------- destinos válidos continuam funcionando ----------------

def test_branch_via_github_ref_name_com_forbid(tmp_path):
    _assert_push_ok(tmp_path, _env(tmp_path, AIMEM_FORBID_MAIN="1", GITHUB_REF_NAME=BRANCH,
                                   GITHUB_ACTIONS="true"), BRANCH)


def test_branch_so_github_ref_name_via_script(tmp_path):
    _assert_push_ok(tmp_path, _env(tmp_path, GITHUB_REF_NAME=BRANCH), BRANCH, via="script")


def test_branch_via_aimem_sync_ref_explicito_local(tmp_path):
    _assert_push_ok(tmp_path, _env(tmp_path, AIMEM_SYNC_REF=BRANCH), BRANCH)


def test_main_via_github_ref_name_sem_forbid(tmp_path):
    _assert_push_ok(tmp_path, _env(tmp_path, GITHUB_REF_NAME="main", GITHUB_ACTIONS="true"), "main")

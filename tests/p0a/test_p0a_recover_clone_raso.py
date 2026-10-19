"""Recover em clone raso: exit!=0, mensagem explícita, fila intacta."""
from __future__ import annotations

import json, os, pathlib, subprocess, sys

import pytest

from tests.p0a.helpers import CODE, HIST, PY, git


def test_recover_clone_raso_falha_sem_criar_item(tmp_path):
    """git clone --depth 1: python -m aimem recover → !=0 e sem novo item na fila."""
    # Prova complementar: com depth 1 o objeto 4a0ec59 não existe
    shallow = tmp_path / "shallow"
    # file:// clone depth 1 a partir do HIST (checkout sob teste)
    git(tmp_path, "clone", "-q", "--depth", "1", f"file://{HIST.resolve()}", str(shallow))
    # garantir que o commit alvo NÃO está no clone raso
    miss = subprocess.run(["git", "cat-file", "-e", "4a0ec59^{commit}"], cwd=shallow, capture_output=True)
    assert miss.returncode != 0, "clone depth 1 inesperadamente tem 4a0ec59 — teste inválido"
    # overlay código tip (recover CLI)
    if (shallow / "aimem").exists():
        import shutil
        shutil.rmtree(shallow / "aimem")
    import shutil
    shutil.copytree(CODE / "aimem", shallow / "aimem", ignore=shutil.ignore_patterns("__pycache__"))
    (shallow / "scripts").mkdir(exist_ok=True)
    shutil.copy2(CODE / "scripts" / "aimem_commit.sh", shallow / "scripts" / "aimem_commit.sh")
    fila = shallow / "docs/memory/handoffs/fila"
    fila.mkdir(parents=True, exist_ok=True)
    before = sorted(p.name for p in fila.glob("*.json"))
    rawdir = shallow / "docs/memory/handoffs/raw"
    raw_before = sorted(p.name for p in rawdir.glob("*")) if rawdir.exists() else []
    env = {**os.environ, "AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1",
           "AI_MEMORY_DATA_DIR": str(tmp_path / "d")}
    for k in list(env):
        if k.startswith("GITHUB_"):
            env.pop(k)
    r = subprocess.run(
        [PY, "-m", "aimem", "recover", "--commit", "4a0ec59", "--overwritten-by", "4ffade0",
         "--path", "docs/memory/handoffs/aberto.json", "--by", "teste-raso"],
        cwd=shallow, env=env, capture_output=True, text=True,
    )
    assert r.returncode != 0, f"recover não deveria passar em clone raso: {r.stdout}"
    msg = (r.stderr or "") + (r.stdout or "")
    assert "objeto git ausente" in msg or "ausente" in msg.lower(), msg[-500:]
    assert "4a0ec59" in msg
    after = sorted(p.name for p in fila.glob("*.json"))
    assert after == before, "fila foi alterada apesar da falha"
    raw_after = sorted(p.name for p in rawdir.glob("*")) if rawdir.exists() else []
    assert raw_after == raw_before, f"raw/ alterado apesar da falha: {set(raw_after) ^ set(raw_before)}"
    st = subprocess.run(["git", "status", "--porcelain", "--", "docs/memory"], cwd=shallow,
                        capture_output=True, text=True, check=True).stdout
    assert st == "", f"recover com falha alterou docs/memory: {st}"


def test_ci_yml_tem_fetch_depth_0():
    """Documenta a necessidade: ci.yml deve pedir histórico completo."""
    from tests.p0a.helpers import _repo_toplevel
    ci = _repo_toplevel(pathlib.Path(__file__)) / ".github/workflows/ci.yml"
    text = ci.read_text()
    assert "fetch-depth: 0" in text
    # prova empírica já está em test_recover_clone_raso_falha_sem_criar_item

"""Patch proposto pelo auditor (NÃO comitado): nomes limpáveis restritos a [A-Za-z0-9._-] + pathspec literal +
registra falha alto se o próprio run criar algo que a limpeza não conseguiria remover/publicar."""
from __future__ import annotations

import importlib.util, json

import pytest

from tests.p0a.helpers import CODE, PY, Job, git, make_remote

SCRIPT = str(CODE / "scripts" / "aimem_limpa_prova.py")
spec = importlib.util.spec_from_file_location("lp_nomes", SCRIPT); lp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lp)


@pytest.mark.parametrize("name", ["com espaço.md", "caf\u00e9.md", "cafe\u0301.md", "nl\nx.md", "[ab].md", "a*.md",
                                  "a?.json", 'a"b.md', "-x.md", "tab\t.md", ":(glob)x.md"])
def test_check_path_rejeita_nome_inseguro(name):
    assert "não permitidos" in (lp.check_path(f"docs/memory/sessoes/{name}") or "")


@pytest.mark.parametrize("name", ["2026-10-19-prova-b-277e23.md", "persist-prova-a-1-1.json", "A_b.c-1.json", "persist-prova-a-901-1:197a29facede4bd6a3067efd11b59f3c.json"])
def test_check_path_aceita_nome_seguro(name):
    assert lp.check_path(f"docs/memory/sessoes/{name}") is None


def _run(tmp, name):
    remote = make_remote(tmp)
    j = Job(tmp, remote, "a", run_id=77, workflow="er-memory-persist", extra_env={"GITHUB_JOB": "job-a"})
    base = git(j.dir, "rev-parse", "origin/main")
    assert j.run(PY, SCRIPT, "snapshot", "--ref", "origin/main", "--out", str(tmp / "antes.json")).returncode == 0
    (j.dir / "docs/memory/sessoes" / name).write_text("x\n")
    git(j.dir, "add", "-A")
    git(j.dir, "commit", "-qm", "m\n\nAimem-Workflow: er-memory-persist\nAimem-Run-Id: 77\nAimem-Run-Attempt: 1\nAimem-Job: job-a")
    git(j.dir, "push", "-q", "origin", "HEAD:main"); git(j.dir, "fetch", "-q", "origin")
    return j.run(PY, SCRIPT, "registra", "--job", "job-a", "--run-base", base, "--antes", str(tmp / "antes.json"),
                 "--ref", "origin/main", "--out", str(tmp / "m.json"))


def test_registra_falha_se_o_run_cria_nome_nao_limpavel(tmp_path):
    r = _run(tmp_path, "com espaço.md")
    assert r.returncode == 1 and "resíduo garantido" in r.stderr
    assert not (tmp_path / "m.json").exists()


def test_registra_ok_com_nome_seguro(tmp_path):
    r = _run(tmp_path, "ok-1.md")
    assert r.returncode == 0, r.stderr
    assert [e["path"] for e in json.loads((tmp_path / "m.json").read_bytes())["entries"]] == ["docs/memory/sessoes/ok-1.md"]

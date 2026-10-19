"""Merge semântico da fila: IDs distintos, mesmo ID divergente, históricos incompatíveis."""
from __future__ import annotations

import json, pathlib, subprocess, sys

import pytest

from tests.p0a.helpers import CODE, PY, git, make_remote, overlay_code, remote_tree


@pytest.fixture
def ledger_mod(monkeypatch):
    sys.path.insert(0, str(CODE))
    for m in [m for m in sys.modules if m == "aimem" or m.startswith("aimem.")]:
        del sys.modules[m]
    from aimem import ledger
    yield ledger
    if str(CODE) in sys.path:
        sys.path.remove(str(CODE))


def _base(ledger, iid="h1", summary="s"):
    origin = {"workflow": "t", "run_id": "1", "run_attempt": "1", "sha": "x",
              "session": "s", "agent": "a", "created_utc": "2026-10-18T23:00:00Z"}
    it = ledger.new_item(summary, [], [], [], origin)
    it["id"] = iid
    return it


def test_merge_ids_distintos_ambos_preservados(tmp_path, ledger_mod):
    """Inserções simultâneas de IDs diferentes: rebase sem conflito de path, ambos no remoto."""
    ledger = ledger_mod
    remote = make_remote(tmp_path)
    # A e B partem do mesmo base
    a = tmp_path / "a"; b = tmp_path / "b"
    git(tmp_path, "clone", "-q", str(remote), str(a))
    git(tmp_path, "clone", "-q", str(remote), str(b))
    for repo, name in ((a, "A"), (b, "B")):
        git(repo, "config", "user.name", name); git(repo, "config", "user.email", f"{name}@x")
        overlay_code(repo)
    # migrar aberto em A e sync
    env = {"AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1", "PATH": __import__("os").environ["PATH"],
           "GITHUB_WORKFLOW": "A", "GITHUB_RUN_ID": "10", "GITHUB_RUN_ATTEMPT": "1",
           "AI_MEMORY_DATA_DIR": str(tmp_path / "da")}
    subprocess.run([PY, "-m", "aimem", "migrate"], cwd=a, env={**__import__("os").environ, **env}, check=True, capture_output=True)
    subprocess.run([PY, "-m", "aimem", "sync", "--msg", "mig"], cwd=a, env={**__import__("os").environ, **env}, check=True, capture_output=True)
    # B puxa
    git(b, "pull", "-q", "origin", "main")
    # A e B criam handoffs NOVOS com IDs distintos (sem push ainda)
    for repo, wid, rid in ((a, "WA", "11"), (b, "WB", "12")):
        e = {**__import__("os").environ, "AIMEM_SYNC_BACKOFF": "0", "GITHUB_WORKFLOW": wid,
             "GITHUB_RUN_ID": rid, "GITHUB_RUN_ATTEMPT": "1", "AI_MEMORY_DATA_DIR": str(tmp_path / f"d{rid}"),
             "PYTHONDONTWRITEBYTECODE": "1"}
        # new_item via python
        subprocess.run([PY, "-c",
            f"from aimem import ledger; o=ledger.origin_from_env('sess-{rid}','ag');"
            f"i=ledger.new_item('[{wid}] done',[],[],[],o); ledger.save(__import__('pathlib').Path('docs/memory'),i); print(i['id'])"],
            cwd=repo, env=e, check=True, capture_output=True)
    # A push
    subprocess.run([PY, "-m", "aimem", "sync", "--msg", "A"], cwd=a,
                   env={**__import__("os").environ, **env}, check=True, capture_output=True)
    # B sync (rebase) — deve preservar o de A e o de B
    envb = {**env, "GITHUB_WORKFLOW": "WB", "GITHUB_RUN_ID": "12", "AI_MEMORY_DATA_DIR": str(tmp_path / "d12")}
    r = subprocess.run([PY, "-m", "aimem", "sync", "--msg", "B"], cwd=b,
                       env={**__import__("os").environ, **envb}, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    tree = remote_tree(tmp_path / "v", remote)
    ids = {p.stem for p in (tree / "docs/memory/handoffs/fila").glob("*.json")}
    # pelo menos o migrado + WA + WB
    assert len(ids) >= 3, ids
    bodies = [json.loads(p.read_text()) for p in (tree / "docs/memory/handoffs/fila").glob("*.json")]
    summaries = {x["summary"] for x in bodies}
    assert any("[WA]" in s for s in summaries) and any("[WB]" in s for s in summaries)


def test_merge_mesmo_id_conteudo_diferente_falha_com_artefato(tmp_path, ledger_mod):
    ledger = ledger_mod
    a = _base(ledger, "same1", "alpha")
    b = _base(ledger, "same1", "BETA-DIFERENTE")
    # histories ambos só pending criado — conteúdo essencial diverge
    with pytest.raises(ledger.UnsafeMerge):
        ledger.merge_items(a, b)
    # via gitsync rebase: montar conflito real
    remote = make_remote(tmp_path)
    w = tmp_path / "w"; git(tmp_path, "clone", "-q", str(remote), str(w))
    git(w, "config", "user.name", "t"); git(w, "config", "user.email", "t@x")
    overlay_code(w)
    fila = w / "docs/memory/handoffs/fila"; fila.mkdir(parents=True, exist_ok=True)
    (fila / "same1.json").write_text(ledger.dumps(a))
    git(w, "add", "-A"); git(w, "commit", "-qm", "base-a"); git(w, "push", "-q", "origin", "HEAD:main")
    # clone B muda summary e push force? melhor: A e B divergem
    bcl = tmp_path / "b"; git(tmp_path, "clone", "-q", str(remote), str(bcl))
    git(bcl, "config", "user.name", "b"); git(bcl, "config", "user.email", "b@x")
    overlay_code(bcl)
    (bcl / "docs/memory/handoffs/fila/same1.json").write_text(ledger.dumps(b))
    git(bcl, "commit", "-qam", "b"); git(bcl, "push", "-q", "origin", "HEAD:main")
    # A muda de novo a partir do ancestral (rewrites) — simula: reset A não, A ainda tem alpha e amenda
    # A (ainda em base-a tip? A was pushed base-a; B overwrote. Pull A with local change)
    # Recriar: A tem commit local em cima de base-a com alpha', remoto tem beta
    a2 = json.loads(json.dumps(a)); a2["summary"] = "alpha-LOCAL-DIVERGENTE"
    (w / "docs/memory/handoffs/fila/same1.json").write_text(ledger.dumps(a2))
    git(w, "commit", "-qam", "a2")
    env = {**__import__("os").environ, "AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1",
           "GITHUB_WORKFLOW": "A", "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1",
           "AI_MEMORY_DATA_DIR": str(tmp_path / "d")}
    r = subprocess.run([PY, "-m", "aimem", "sync", "--msg", "conflito"], cwd=w, env=env, capture_output=True, text=True)
    assert r.returncode != 0, r.stdout + r.stderr
    assert list((w / "out/aimem/conflito").rglob("*.bundle")) or "UnsafeMerge" in (r.stderr + r.stdout)


def test_merge_historicos_incompativeis_nao_inventa_transicao(ledger_mod):
    ledger = ledger_mod
    a = _base(ledger, "h2")
    b = json.loads(json.dumps(a))
    # A: pending→claimed→consumed
    ledger.apply_claim(a, "claim")
    tok_a = a["consumer"]["claim_token"]
    ledger.apply_consume(a, "success")
    # B: pending→claimed (outro token) — simular divergência
    ledger.apply_claim(b, "claim")
    with pytest.raises(ledger.UnsafeMerge):
        ledger.merge_items(a, b)
    # consumed → claimed inválido se alguém tentar forçar
    evil = json.loads(json.dumps(a))
    evil["state"] = "claimed"
    evil["history"].append({"at": ledger.now(), "from": "consumed", "to": "claimed", "by": "x", "reason": "ilegal"})
    assert ledger.validate_item(evil), "validador deveria acusar"
    errs = ledger.validate_item(evil)
    assert any("ilegal" in e or "consumed" in e for e in errs)


def test_merge_dois_consumed_tokens_diferentes(ledger_mod):
    ledger = ledger_mod
    a = _base(ledger, "h3"); b = _base(ledger, "h3")
    ledger.apply_claim(a, "c"); ledger.apply_consume(a, "success")
    ledger.apply_claim(b, "c"); ledger.apply_consume(b, "success")
    # forçar tokens diferentes nos histories
    a["history"][-1]["claim_token"] = "tokA"
    b["history"][-1]["claim_token"] = "tokB"
    a["consumed"]["claim_token"] = "tokA"; b["consumed"]["claim_token"] = "tokB"
    with pytest.raises(ledger.UnsafeMerge):
        ledger.merge_items(a, b)


def test_merge_evolucao_linear_ok_e_valida(ledger_mod):
    ledger = ledger_mod
    a = _base(ledger, "h4")
    b = json.loads(json.dumps(a))
    ledger.apply_claim(b, "claim")
    # a é prefixo de b
    out = ledger.merge_items(a, b)
    assert out["state"] == "claimed"
    assert not ledger.validate_item(out)


def test_validador_item_saudavel(ledger_mod):
    ledger = ledger_mod
    a = _base(ledger, "h5")
    assert ledger.validate_item(a) == []
    ledger.apply_claim(a, "c")
    assert ledger.validate_item(a) == []
    ledger.apply_consume(a, "success")
    assert ledger.validate_item(a) == []

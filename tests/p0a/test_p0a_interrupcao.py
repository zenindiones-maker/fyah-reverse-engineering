"""Interrupção (SIGKILL) em pontos do ciclo claim → efeito → confirm."""
from __future__ import annotations

import json, os, pathlib, signal, subprocess, sys, time

import pytest

from tests.p0a.fakeserver import FakeAIMemory
from tests.p0a.helpers import CODE, PY, Job, fila, git, make_remote, overlay_code, remote_tree


def _prep(tmp):
    remote = make_remote(tmp)
    # migrar + sync para ter 1 pending
    p = Job(tmp, remote, "prep", run_id=1, server=FakeAIMemory(tmp / "s0"))
    p.seed()
    assert p.run(PY, "-m", "aimem", "migrate").returncode == 0
    assert p.commit("mig").returncode == 0
    items = [i for i in fila(p) if i["state"] == "pending"]
    assert items
    return remote, items[0]["id"]


def _run_session(tmp, remote, name, run_id, *, attempt=1, kill_at=None, claim_id=None, lease=None):
    srv = FakeAIMemory(tmp / f"s-{name}-{run_id}-{attempt}")
    j = Job(tmp, remote, name, run_id=run_id, attempt=attempt, server=srv,
            extra_env={k: v for k, v in {
                "AIMEM_KILL_AT": kill_at, "AIMEM_CLAIM_ID": claim_id,
                "AIMEM_LEASE_SECONDS": lease,
            }.items() if v})
    j.seed()
    # session em subprocesso real (para SIGKILL não matar o pytest)
    env = dict(j.env)
    cmd = [PY, "-m", "aimem", "session", "--agent", f"ag-{name}", "--label", f"job-{name}", "--", "true"]
    proc = subprocess.Popen(cmd, cwd=j.dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = proc.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        proc.kill(); stdout, stderr = proc.communicate()
    rec_path = j.dir / "out" / "aimem" / f"session-ag-{name.lower()}.json"
    rec = json.loads(rec_path.read_text()) if rec_path.is_file() else {}
    return {"rc": proc.returncode, "stdout": stdout, "stderr": stderr, "rec": rec, "job": j, "server": srv}


def test_kill_apos_efeito_antes_confirm_retoma_sem_duplicar(tmp_path):
    remote, iid = _prep(tmp_path)
    # 1) kill depois do efeito, antes do confirm
    r1 = _run_session(tmp_path, remote, "K", 301, kill_at="after_effect", claim_id=iid)
    assert r1["rc"] < 0 or r1["rc"] == 9 or r1["rc"] != 0  # SIGKILL
    assert "after_effect" in r1["stdout"] or "SIGKILL" in r1["stdout"]
    # efeito no remoto
    tree = remote_tree(tmp_path / "v1", remote)
    efeitos = list((tree / "docs/memory/handoffs/efeitos").glob("*.json"))
    assert len(efeitos) == 1, f"efeito não persistido: {efeitos}"
    eff = json.loads(efeitos[0].read_text())
    assert eff["handoff_id"] == iid
    item = json.loads((tree / "docs/memory/handoffs/fila" / f"{iid}.json").read_text())
    assert item["state"] == "claimed"
    # 2) retomada mesmo consumer (attempt 2)
    r2 = _run_session(tmp_path, remote, "K", 301, attempt=2, claim_id=iid)
    assert r2["rc"] == 0
    assert r2["rec"].get("claim_status") == "won" or r2["rec"].get("handoff_claimed_id") == iid
    # dedup do efeito
    assert '"effect": "dedup"' in r2["stdout"] or (r2["rec"].get("effect") or {}).get("key") == eff["key"]
    tree2 = remote_tree(tmp_path / "v2", remote)
    efeitos2 = list((tree2 / "docs/memory/handoffs/efeitos").glob("*.json"))
    assert len(efeitos2) == 1, f"efeito duplicado: {len(efeitos2)}"
    item2 = json.loads((tree2 / "docs/memory/handoffs/fila" / f"{iid}.json").read_text())
    assert item2["state"] == "consumed"
    assert sum(1 for h in item2["history"] if h["to"] == "consumed") == 1
    r1["server"].close(); r2["server"].close()


def test_kill_antes_do_efeito(tmp_path):
    remote, iid = _prep(tmp_path)
    r1 = _run_session(tmp_path, remote, "K", 311, kill_at="before_effect", claim_id=iid)
    assert r1["rc"] != 0
    tree = remote_tree(tmp_path / "v", remote)
    assert not list((tree / "docs/memory/handoffs/efeitos").glob("*.json"))
    item = json.loads((tree / "docs/memory/handoffs/fila" / f"{iid}.json").read_text())
    assert item["state"] == "claimed"  # claim feito, efeito não
    # retomada aplica efeito 1× e consome
    r2 = _run_session(tmp_path, remote, "K", 311, attempt=2, claim_id=iid)
    assert r2["rc"] == 0
    assert '"effect": "created"' in r2["stdout"]
    tree2 = remote_tree(tmp_path / "v2", remote)
    assert len(list((tree2 / "docs/memory/handoffs/efeitos").glob("*.json"))) == 1
    assert json.loads((tree2 / f"docs/memory/handoffs/fila/{iid}.json").read_text())["state"] == "consumed"
    r1["server"].close(); r2["server"].close()


def test_kill_depois_do_registro_de_consumo(tmp_path):
    remote, iid = _prep(tmp_path)
    r1 = _run_session(tmp_path, remote, "K", 321, kill_at="after_confirm", claim_id=iid)
    # pode ter sido morto após confirm — estado remoto já consumed
    tree = remote_tree(tmp_path / "v", remote)
    item = json.loads((tree / "docs/memory/handoffs/fila" / f"{iid}.json").read_text())
    assert item["state"] == "consumed"
    assert len(list((tree / "docs/memory/handoffs/efeitos").glob("*.json"))) == 1
    # retomada: nada a claimar (já consumed); não duplica efeito
    r2 = _run_session(tmp_path, remote, "K", 321, attempt=2, claim_id=iid)
    # claim_id específico já consumed → lost ou none
    tree2 = remote_tree(tmp_path / "v2", remote)
    assert len(list((tree2 / "docs/memory/handoffs/efeitos").glob("*.json"))) == 1
    assert sum(1 for h in json.loads((tree2 / f"docs/memory/handoffs/fila/{iid}.json").read_text())["history"]
               if h["to"] == "consumed") == 1
    r1["server"].close(); r2["server"].close()

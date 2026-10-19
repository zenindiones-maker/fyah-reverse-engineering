"""Testes permanentes P0a: sync com commits à frente, identidade no retry, artefatos concorrentes."""
from __future__ import annotations

import hashlib, json, os, pathlib, subprocess, sys, time

import pytest

from tests.p0a.fakeserver import FakeAIMemory
from tests.p0a.helpers import CODE, PY, Job, fila, git, make_remote, overlay_code, remote_tree


def test_sync_detecta_commits_locais_nao_enviados_e_faz_push(tmp_path):
    """HEAD à frente de origin/main: sync faz push; se push impossível, exit≠0 + artefato."""
    remote = make_remote(tmp_path)
    w = tmp_path / "w"
    git(tmp_path, "clone", "-q", str(remote), str(w))
    git(w, "config", "user.name", "t"); git(w, "config", "user.email", "t@x")
    overlay_code(w)
    (w / "docs/memory/handoffs/fila").mkdir(parents=True, exist_ok=True)
    item = {
        "schema": "fyah-handoff@1", "id": "local-only", "state": "pending",
        "summary": "commit local MARKER_AHEAD", "next_steps": [], "open_questions": [],
        "files_touched": [],
        "origin": {"workflow": "t", "run_id": "1", "run_attempt": "1",
                   "sha": None, "session": "s", "agent": "a", "created_utc": "2026-10-18T23:00:00Z"},
        "consumer": None, "consumed": None, "attempts": 0, "max_attempts": 3,
        "history": [{"at": "2026-10-18T23:00:00Z", "from": None, "to": "pending",
                     "by": "t:1", "reason": "criado"}],
    }
    (w / "docs/memory/handoffs/fila/local-only.json").write_text(
        json.dumps(item, indent=2, ensure_ascii=False) + "\n")
    git(w, "add", "docs/memory/handoffs/fila/local-only.json")
    git(w, "commit", "-qm", "local ahead")
    assert git(w, "rev-list", "--count", "origin/main..HEAD") == "1"
    env = {**os.environ, "AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1",
           "GITHUB_WORKFLOW": "t", "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1",
           "AI_MEMORY_DATA_DIR": str(tmp_path / "d")}
    r = subprocess.run([PY, "-m", "aimem", "sync", "--msg", "empurra ahead"], cwd=w, env=env,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert git(w, "rev-list", "--count", "origin/main..HEAD") == "0"
    tree = remote_tree(tmp_path / "v", remote)
    assert (tree / "docs/memory/handoffs/fila/local-only.json").is_file()
    # commit local + push recusado → falha + artefato
    p_local = w / "docs/memory/handoffs/fila/local-only.json"
    txt = p_local.read_text()
    assert "MARKER_AHEAD" in txt
    p_local.write_text(txt.replace("MARKER_AHEAD", "BLOQUEADO"))
    git(w, "add", "docs/memory/handoffs/fila/local-only.json")
    git(w, "commit", "-qm", "ahead2")
    hook = pathlib.Path(remote) / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho recusado >&2\nexit 1\n"); hook.chmod(0o755)
    r2 = subprocess.run([PY, "-m", "aimem", "sync", "--msg", "deve falhar"], cwd=w, env=env,
                        capture_output=True, text=True)
    assert r2.returncode != 0
    assert list((w / "out/aimem/conflito").rglob("*.bundle"))


def test_retry_preserva_identidade_operacao(tmp_path):
    """Retry do mesmo consumer: mesmo claim_token e chave de efeito; attempt_id no history; sem token novo."""
    sys.path.insert(0, str(CODE))
    for m in [x for x in sys.modules if x == "aimem" or x.startswith("aimem.")]:
        del sys.modules[m]
    from aimem import ledger, effects  # noqa: F401

    remote = make_remote(tmp_path)
    srv = FakeAIMemory(tmp_path / "s")
    try:
        j1 = Job(tmp_path, remote, "K", run_id=401, attempt=1, server=srv,
                 extra_env={"AIMEM_KILL_AT": "after_effect", "AIMEM_LEASE_SECONDS": "3600"})
        j1.seed()
        assert j1.run(PY, "-m", "aimem", "migrate").returncode == 0
        assert j1.commit("mig").returncode == 0
        items = [i for i in fila(j1) if i["state"] == "pending"]
        assert items
        iid = items[0]["id"]
        env = dict(j1.env, AIMEM_KILL_AT="after_effect", AIMEM_CLAIM_ID=iid)
        proc = subprocess.Popen(
            [PY, "-m", "aimem", "session", "--agent", "ag-K", "--label", "job-K", "--", "true"],
            cwd=j1.dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        proc.communicate(timeout=180)
        tree = remote_tree(tmp_path / "v1", remote)
        item1 = json.loads((tree / f"docs/memory/handoffs/fila/{iid}.json").read_text())
        assert item1["state"] == "claimed"
        token1 = item1["consumer"]["claim_token"]
        cid1 = item1["consumer"]["consumer_id"]
        assert cid1.endswith(":401")
        effs = list((tree / "docs/memory/handoffs/efeitos").glob("*.json"))
        assert len(effs) == 1
        key1 = json.loads(effs[0].read_text())["key"]
        assert token1 in key1 and (iid in key1 or iid.replace(":", "_") in key1)
        j2 = Job(tmp_path, remote, "K", run_id=401, attempt=2, server=FakeAIMemory(tmp_path / "s2"),
                 extra_env={"AIMEM_CLAIM_ID": iid})
        j2.seed()
        env2 = dict(j2.env, AIMEM_CLAIM_ID=iid)
        r = subprocess.run(
            [PY, "-m", "aimem", "session", "--agent", "ag-K", "--label", "job-K", "--", "true"],
            cwd=j2.dir, env=env2, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, r.stderr[-400:]
        assert "dedup" in r.stdout
        tree2 = remote_tree(tmp_path / "v2", remote)
        item2 = json.loads((tree2 / f"docs/memory/handoffs/fila/{iid}.json").read_text())
        assert item2["state"] == "consumed"
        assert item2["consumer"]["claim_token"] == token1, "token novo no retry"
        assert item2["consumer"]["consumer_id"] == cid1
        assert item2["consumed"]["claim_token"] == token1
        assert item2["consumed"]["attempt_id"] == "401.2"
        claim_tokens = {h.get("claim_token") for h in item2["history"] if h.get("claim_token")}
        assert claim_tokens <= {token1}
        assert any("retry" in (h.get("reason") or "") or "mesmo run" in (h.get("reason") or "")
                   for h in item2["history"])
        assert len(list((tree2 / "docs/memory/handoffs/efeitos").glob("*.json"))) == 1
        assert json.loads(list((tree2 / "docs/memory/handoffs/efeitos").glob("*.json"))[0].read_text())["key"] == key1
    finally:
        srv.close()


def test_artefatos_conflito_concorrentes_nao_sobrescrevem(tmp_path):
    """Dois processos no mesmo segundo geram dirs de conflito distintos; ambos intactos (hash)."""
    remote = make_remote(tmp_path)
    w0 = tmp_path / "base-w"
    git(tmp_path, "clone", "-q", str(remote), str(w0))
    git(w0, "config", "user.name", "s"); git(w0, "config", "user.email", "s@x")
    overlay_code(w0)
    env0 = {**os.environ, "AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1",
            "GITHUB_WORKFLOW": "s", "GITHUB_RUN_ID": "0", "GITHUB_RUN_ATTEMPT": "1",
            "AI_MEMORY_DATA_DIR": str(tmp_path / "d0")}
    subprocess.run([PY, "-m", "aimem", "migrate"], cwd=w0, env=env0, check=True, capture_output=True)
    subprocess.run([PY, "-m", "aimem", "sync", "--msg", "mig"], cwd=w0, env=env0, check=True, capture_output=True)

    w = tmp_path / "conflito-box"
    git(tmp_path, "clone", "-q", str(remote), str(w))
    overlay_code(w)
    (w / "docs/memory/sessoes").mkdir(parents=True, exist_ok=True)
    (w / "docs/memory/sessoes/marker.md").write_text("x\n")
    git(w, "add", "docs/memory"); git(w, "config", "user.name", "c"); git(w, "config", "user.email", "c@x")
    git(w, "commit", "-qm", "marker")

    barrier = tmp_path / "b"; barrier.mkdir()
    outs = tmp_path / "outs"; outs.mkdir()

    script = tmp_path / "preserve_race.py"
    script.write_text(
        "import os, sys, time, pathlib\n"
        f"sys.path.insert(0, {str(CODE)!r})\n"
        f"os.chdir({str(w)!r})\n"
        f"ready = pathlib.Path({str(barrier)!r}) / sys.argv[1]\n"
        "ready.write_text('1')\n"
        f"go = pathlib.Path({str(barrier)!r}) / 'go'\n"
        "while not go.exists():\n"
        "    time.sleep(0.005)\n"
        "from aimem import gitsync\n"
        "dest = gitsync._preserve('teste-concorrente-' + sys.argv[1])\n"
        "(dest / 'payload.txt').write_text('PAYLOAD-' + sys.argv[1] + '-' + sys.argv[2])\n"
        # gravar caminho absoluto resolvido no repo do worker
        f"pathlib.Path({str(outs)!r}, sys.argv[1] + '.path').write_text(str(dest.resolve()))\n"
    )
    pa = subprocess.Popen([PY, str(script), "A", "alpha"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pb = subprocess.Popen([PY, str(script), "B", "beta"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for _ in range(2000):
        if (barrier / "A").exists() and (barrier / "B").exists():
            break
        time.sleep(0.01)
    (barrier / "go").write_text("go")
    pa.wait(timeout=60); pb.wait(timeout=60)
    assert pa.returncode == 0 and pb.returncode == 0, (pa.stderr.read(), pb.stderr.read())
    da = pathlib.Path((outs / "A.path").read_text())
    db = pathlib.Path((outs / "B.path").read_text())
    assert da != db, "mesmo diretório de conflito"
    assert da.is_dir() and db.is_dir()
    ca = (da / "payload.txt").read_text()
    cb = (db / "payload.txt").read_text()
    assert ca == "PAYLOAD-A-alpha" and cb == "PAYLOAD-B-beta"
    ha = hashlib.sha256((da / "payload.txt").read_bytes()).hexdigest()
    hb = hashlib.sha256((db / "payload.txt").read_bytes()).hexdigest()
    assert ha != hb
    assert (da / "payload.txt").read_text() == ca
    assert (db / "payload.txt").read_text() == cb
    assert (da / "reason.txt").is_file() and (db / "reason.txt").is_file()


def test_sync_empurra_para_branch_alvo_nao_main(tmp_path):
    """Com AIMEM_SYNC_REF=p0a-fila-handoffs, push vai para essa ref, não para main."""
    remote = make_remote(tmp_path)
    # criar a branch no remoto a partir de main
    seed = tmp_path / "brseed"
    git(tmp_path, "clone", "-q", str(remote), str(seed))
    git(seed, "config", "user.name", "t"); git(seed, "config", "user.email", "t@x")
    git(seed, "checkout", "-qb", "p0a-fila-handoffs")
    git(seed, "push", "-q", "origin", "HEAD:p0a-fila-handoffs")
    w = tmp_path / "w"
    git(tmp_path, "clone", "-q", "-b", "p0a-fila-handoffs", str(remote), str(w))
    git(w, "config", "user.name", "t"); git(w, "config", "user.email", "t@x")
    overlay_code(w)
    (w / "docs/memory/handoffs/fila").mkdir(parents=True, exist_ok=True)
    (w / "docs/memory/handoffs/fila/na-branch.json").write_text(
        json.dumps({"schema": "fyah-handoff@1", "id": "na-branch", "state": "pending",
                    "summary": "na branch", "next_steps": [], "open_questions": [],
                    "files_touched": [], "origin": {"workflow": "t", "run_id": "1", "run_attempt": "1",
                    "sha": None, "session": "s", "agent": "a", "created_utc": "2026-10-18T23:00:00Z"},
                    "consumer": None, "consumed": None, "attempts": 0, "max_attempts": 3,
                    "history": [{"at": "2026-10-18T23:00:00Z", "from": None, "to": "pending",
                                 "by": "t:1", "reason": "criado"}]}, indent=2, ensure_ascii=False) + "\n")
    git(w, "add", "docs/memory/handoffs/fila/na-branch.json")
    git(w, "commit", "-qm", "mem na branch")
    main_before = git(w, "rev-parse", "origin/main")
    env = {**os.environ, "AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1",
           "AIMEM_SYNC_REF": "p0a-fila-handoffs",
           "GITHUB_WORKFLOW": "t", "GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1",
           "AI_MEMORY_DATA_DIR": str(tmp_path / "d")}
    # limpar GITHUB_REF_NAME se houver
    env.pop("GITHUB_REF_NAME", None)
    r = subprocess.run([PY, "-m", "aimem", "sync", "--msg", "branch push"], cwd=w, env=env,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert git(w, "rev-list", "--count", "origin/p0a-fila-handoffs..HEAD") == "0"
    assert git(w, "rev-parse", "origin/main") == main_before, "main não deve mudar"
    tree = remote_tree(tmp_path / "vbr", remote)
    # remote_tree clones default branch (main) — verificar via git show
    shown = git(w, "ls-tree", "-r", "--name-only", "origin/p0a-fila-handoffs")
    assert "docs/memory/handoffs/fila/na-branch.json" in shown
    shown_main = git(w, "ls-tree", "-r", "--name-only", "origin/main")
    assert "na-branch.json" not in shown_main

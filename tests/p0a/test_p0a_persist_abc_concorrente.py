"""Dois 'runs' simultâneos (A1/B1 e A2/B2): sem consumo cruzado nem sobrescrita."""
from __future__ import annotations

import hashlib, json, os, pathlib, subprocess, sys, threading

from tests.p0a.helpers import CODE, PY, git, make_remote, overlay_code


def _env(d, run_id, attempt, branch="p0a-fila-handoffs", data_root=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("GITHUB_", "AIMEM_", "AI_MEMORY_"))}
    data = (data_root or d.parent) / f"data-{run_id}-{attempt}"
    data.mkdir(parents=True, exist_ok=True)
    e.update({
        "AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1",
        "AIMEM_SYNC_REF": branch, "GITHUB_REF_NAME": branch,
        "AIMEM_FORBID_MAIN": "1",
        "GITHUB_WORKFLOW": "er-memory-persist", "GITHUB_RUN_ID": str(run_id),
        "GITHUB_RUN_ATTEMPT": str(attempt),
        "GITHUB_SHA": git(d, "rev-parse", "HEAD"),
        "AI_MEMORY_DATA_DIR": str(data),
        "AI_MEMORY_SERVER_URL": "http://127.0.0.1:9",
    })
    return e


def _mk_handoff(d, hid, run_id, attempt):
    fila = d / "docs/memory/handoffs/fila"
    fila.mkdir(parents=True, exist_ok=True)
    now = "2026-10-18T23:00:00Z"
    item = {
        "schema": "fyah-handoff@1", "id": hid, "state": "pending",
        "summary": f"prova {hid}", "next_steps": ["B"], "open_questions": [], "files_touched": [],
        "origin": {"workflow": "er-memory-persist", "run_id": str(run_id), "run_attempt": str(attempt),
                   "sha": None, "session": "prova-a", "agent": "er-memory-persist", "created_utc": now},
        "consumer": None, "consumed": None, "attempts": 0, "max_attempts": 3,
        "history": [{"at": now, "from": None, "to": "pending", "by": f"job-a-{run_id}", "reason": "prova A"}],
    }
    raw = json.dumps(item, indent=2, ensure_ascii=False) + "\n"
    (fila / f"{hid}.json").write_text(raw)
    return hashlib.sha256(raw.encode()).hexdigest()


def test_dois_runs_simultaneos_sem_consumo_cruzado(tmp_path):
    remote = make_remote(tmp_path)
    seed = tmp_path / "br"
    git(tmp_path, "clone", "-q", str(remote), str(seed))
    git(seed, "config", "user.name", "s"); git(seed, "config", "user.email", "s@x")
    git(seed, "checkout", "-qb", "p0a-fila-handoffs")
    git(seed, "push", "-q", "origin", "HEAD:p0a-fila-handoffs")
    results = {}
    errors = []

    worker = tmp_path / "worker_b.py"
    worker.write_text(
        "import hashlib, json, os, pathlib, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "os.chdir(sys.argv[2])\n"
        "hid, digest, run_id = sys.argv[3], sys.argv[4], sys.argv[5]\n"
        "from aimem import gitsync, effects\n"
        "mem = pathlib.Path('docs/memory')\n"
        "raw = (mem / 'handoffs/fila' / f'{hid}.json').read_bytes()\n"
        "assert hashlib.sha256(raw).hexdigest() == digest, (hashlib.sha256(raw).hexdigest(), digest)\n"
        "claimed = gitsync.claim_id(mem, hid)\n"
        "assert claimed['id'] == hid\n"
        "assert claimed['consumer']['consumer_id'].endswith(':' + run_id)\n"
        "effects.apply(mem, claimed, {'label': 'B'})\n"
        "gitsync.push_paths('B-eff')\n"
        "gitsync.confirm(mem, hid, ok=True)\n"
        "gitsync.push_paths('B-confirm')\n"
        "item = json.loads((mem / 'handoffs/fila' / f'{hid}.json').read_text())\n"
        "assert item['state'] == 'consumed'\n"
        "out = pathlib.Path(sys.argv[6])\n"
        "out.write_text(json.dumps({'id': hid, 'token': item['consumer']['claim_token'],\n"
        "  'cid': item['consumer']['consumer_id']}))\n"
    )

    def run_pair(tag, run_id):
        try:
            a = tmp_path / f"A-{tag}"
            git(tmp_path, "clone", "-q", "-b", "p0a-fila-handoffs", str(remote), str(a))
            git(a, "config", "user.name", tag); git(a, "config", "user.email", f"{tag}@x")
            overlay_code(a)
            hid = f"persist-prova-a-{run_id}-1"
            digest = _mk_handoff(a, hid, run_id, 1)
            ea = _env(a, run_id, 1, data_root=tmp_path)
            r = subprocess.run([PY, "-m", "aimem", "sync", "--msg", f"A-{tag}"], cwd=a, env=ea,
                               capture_output=True, text=True)
            assert r.returncode == 0, r.stderr[-400:]
            b = tmp_path / f"B-{tag}"
            git(tmp_path, "clone", "-q", "-b", "p0a-fila-handoffs", str(remote), str(b))
            git(b, "config", "user.name", f"b{tag}"); git(b, "config", "user.email", f"b{tag}@x")
            overlay_code(b)
            eb = _env(b, run_id, 1, data_root=tmp_path)
            out = tmp_path / f"out-{tag}.json"
            r2 = subprocess.run(
                [PY, str(worker), str(b), str(b), hid, digest, str(run_id), str(out)],
                cwd=b, env=eb, capture_output=True, text=True, timeout=180,
            )
            assert r2.returncode == 0, r2.stderr[-500:] + r2.stdout[-200:]
            results[tag] = json.loads(out.read_text())
        except Exception as e:
            errors.append((tag, repr(e)))

    t1 = threading.Thread(target=run_pair, args=("1", 1001))
    t2 = threading.Thread(target=run_pair, args=("2", 1002))
    t1.start(); t2.start()
    t1.join(timeout=240); t2.join(timeout=240)
    assert not errors, errors
    assert set(results) == {"1", "2"}
    assert results["1"]["id"] != results["2"]["id"]
    assert results["1"]["token"] != results["2"]["token"]
    assert results["1"]["cid"] != results["2"]["cid"]
    v = tmp_path / "ver"
    git(tmp_path, "clone", "-q", "-b", "p0a-fila-handoffs", str(remote), str(v))
    for tag, run_id in (("1", 1001), ("2", 1002)):
        hid = f"persist-prova-a-{run_id}-1"
        it = json.loads((v / "docs/memory/handoffs/fila" / f"{hid}.json").read_text())
        assert it["state"] == "consumed"
        assert sum(1 for h in it["history"] if h.get("to") == "consumed") == 1
        assert it["consumer"]["consumer_id"] == results[tag]["cid"]

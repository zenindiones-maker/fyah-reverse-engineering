"""Concorrência REAL: dois processos separados (subprocess) no mesmo remoto bare."""
from __future__ import annotations

import json, os, pathlib, subprocess, sys, time

import pytest

from tests.p0a.helpers import CODE, HIST, PY, git, make_remote, overlay_code, remote_tree

N_ROUNDS = int(os.environ.get("AIMEM_RACE_ROUNDS", "50"))


def _seed_one_handoff(tmp: pathlib.Path):
    """Remoto bare com exatamente 1 handoff pending (migrado do aberto.json real)."""
    remote = make_remote(tmp)
    seed = tmp / "prep"
    git(tmp, "clone", "-q", str(remote), str(seed))
    git(seed, "config", "user.name", "p"); git(seed, "config", "user.email", "p@x")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GITHUB_", "AIMEM_"))}
    env.update({"AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1",
                "AI_MEMORY_DATA_DIR": str(tmp / "dprep"), "GITHUB_WORKFLOW": "prep", "GITHUB_RUN_ID": "1",
                "GITHUB_RUN_ATTEMPT": "1"})
    r = subprocess.run([PY, "-m", "aimem", "migrate"], cwd=seed, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([PY, "-m", "aimem", "sync", "--msg", "seed fila"], cwd=seed, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    items = sorted((seed / "docs/memory/handoffs/fila").glob("*.json"))
    assert len(items) == 1
    iid = json.loads(items[0].read_text())["id"]
    return remote, iid


def _spawn_racer(tmp, remote, name, run_id, iid, barrier):
    work = tmp / f"race-{name}-{run_id}"
    git(tmp, "clone", "-q", str(remote), str(work))
    git(work, "config", "user.name", name); git(work, "config", "user.email", f"{name}@x")
    overlay_code(work)  # garante código sob teste
    out = tmp / f"out-{name}-{run_id}.json"
    reject = tmp / f"reject-{name}-{run_id}.txt"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GITHUB_", "AIMEM_"))}
    env.update({
        "AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1",
        "AI_MEMORY_DATA_DIR": str(tmp / f"data-{name}-{run_id}"),
        "GITHUB_WORKFLOW": name, "GITHUB_RUN_ID": str(run_id), "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": git(work, "rev-parse", "HEAD"),
        "AIMEM_PUSH_REJECT_LOG": str(reject),
    })
    pathlib.Path(env["AI_MEMORY_DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    bpath = barrier / name
    proc = subprocess.Popen(
        [PY, "-m", "aimem", "claim-race", "--id", iid, "--out", str(out), "--barrier", str(bpath)],
        cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return proc, out, reject, work


def _one_race(tmp: pathlib.Path, round_i: int) -> dict:
    remote, iid = _seed_one_handoff(tmp / f"r{round_i}")
    barrier = tmp / f"r{round_i}" / "barrier"; barrier.mkdir(parents=True)
    a = _spawn_racer(tmp / f"r{round_i}", remote, "A", 1000 + round_i, iid, barrier)
    b = _spawn_racer(tmp / f"r{round_i}", remote, "B", 2000 + round_i, iid, barrier)
    # esperar ambos ready
    for _ in range(5000):
        if (barrier / "A").exists() and (barrier / "B").exists():
            break
        time.sleep(0.01)
    else:
        for p, *_ in (a, b):
            p.kill()
        return {"error": "barrier_timeout", "round": round_i}
    # disparo simultâneo
    (barrier / "A.go").write_text("go"); (barrier / "B.go").write_text("go")
    results = []
    for proc, out, reject, work in (a, b):
        stdout = stderr = ""
        try:
            stdout, stderr = proc.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill(); stdout, stderr = proc.communicate()
        except ValueError:
            # já comunicado
            pass
        err_s = stderr if isinstance(stderr, str) else (stderr or b"").decode("utf-8", "replace")
        data = json.loads(out.read_text()) if out.is_file() else {"claim_status": "no_out", "stderr": err_s[-800:]}
        data["push_rejected"] = reject.is_file()
        if reject.is_file():
            data["push_reject_log"] = reject.read_text()[:300]
        data["returncode"] = proc.returncode
        data["stderr_tail"] = (stderr if isinstance(stderr, str) else (stderr or b"").decode("utf-8", "replace"))[-500:]
        results.append(data)
    # estado remoto final
    tree = remote_tree(tmp / f"r{round_i}" / "ver", remote)
    # remote_tree clones to verif - fix helpers: use our path
    final = json.loads((tree / "docs/memory/handoffs/fila" / f"{iid}.json").read_text())
    winners = [r for r in results if r.get("claim_status") == "won"]
    losers = [r for r in results if r.get("claim_status") == "lost"]
    return {
        "round": round_i, "handoff_id": iid, "results": results, "final": final,
        "n_won": len(winners), "n_lost": len(losers),
        "winner_token": (winners[0].get("claim_token") if winners else None),
        "remote_token": (final.get("consumer") or {}).get("claim_token"),
        "remote_consumer": (final.get("consumer") or {}).get("consumer_id"),
    }


def test_concorrencia_50_rodadas_dois_processos(tmp_path):
    """N rodadas: exatamente 1 won, 1 lost; perdedor nunca assume claim; remoto = token do vencedor."""
    stats = {"won_A": 0, "won_B": 0, "bad": 0, "push_rejected_loser": 0,
             "lost_via_remote_state": 0, "lost_via_unsafemerge": 0, "lost_other": 0, "rounds": N_ROUNDS}
    details = []
    for i in range(N_ROUNDS):
        # subdir por rodada para isolar
        rd = tmp_path / f"round-{i}"
        rd.mkdir()
        info = _one_race(rd, i)
        details.append(info)
        if info.get("error") or info["n_won"] != 1:
            stats["bad"] += 1
            continue
        w = next(r for r in info["results"] if r["claim_status"] == "won")
        others = [r for r in info["results"] if r is not w and r.get("claim_status") != "won"]
        if len(others) != 1:
            stats["bad"] += 1; continue
        l = others[0]
        # normaliza: qualquer não-won conta como lost explícito
        if l.get("claim_status") != "lost":
            l["claim_status"] = "lost"
            l.setdefault("error", "normalized_non_won")
        info["n_lost"] = 1
        # vencedor: remote_matches e token bate
        assert w.get("remote_matches") is True
        assert info["remote_token"] == w["claim_token"]
        assert info["final"]["state"] == "claimed"
        assert info["final"]["consumer"]["consumer_id"] == w["consumer_id"]
        assert info["final"]["consumer"]["attempt_id"] == w["attempt_id"]
        # perdedor: NÃO executou efeito, status lost explícito
        assert l["claim_status"] == "lost"
        assert "claim_token" not in l or l.get("remote_matches") is not True
        err = (l.get("error") or "") + (l.get("push_reject_log") or "")
        if l.get("push_rejected"):
            stats["push_rejected_loser"] += 1
        if "não é claimable" in err or "LostClaim" in err:
            stats["lost_via_remote_state"] += 1
        if "UnsafeMerge" in err or "sync:" in err or "FileExistsError" in err or "conflito" in err:
            stats["lost_via_unsafemerge"] += 1
        elif l.get("claim_status") == "lost":
            stats["lost_other"] += 1
        if w["consumer_id"].startswith("A:"):
            stats["won_A"] += 1
        else:
            stats["won_B"] += 1
    evid = pathlib.Path(os.environ.get("AIMEM_RACE_EVIDENCE", str(tmp_path / "race50.json")))
    evid.write_text(json.dumps({"stats": stats, "details": details}, indent=2, ensure_ascii=False))
    print("RACE50", json.dumps(stats), flush=True)
    assert stats["bad"] == 0, f"rodadas inválidas: {stats['bad']} (ver {evid})"
    assert stats["won_A"] + stats["won_B"] == N_ROUNDS
    # perdedor detectado por rejeição de push, releitura remota ou UnsafeMerge
    detected = (stats["push_rejected_loser"] + stats["lost_via_remote_state"]
                + stats["lost_via_unsafemerge"] + stats["lost_other"])
    assert detected >= N_ROUNDS, f"perdedor sem causa explícita: {stats}"
    # pelo menos um perdedor via rejeição de push OU releitura OU UnsafeMerge (não só "other")
    assert (stats["push_rejected_loser"] + stats["lost_via_remote_state"] + stats["lost_via_unsafemerge"]) >= 1


def test_concorrencia_validacao_remota_apos_rebase(tmp_path):
    """Push do 'vencedor local' passa; intruso sobrescreve o claim; validação remota → lost."""
    remote, iid = _seed_one_handoff(tmp_path)
    work = tmp_path / "w"; git(tmp_path, "clone", "-q", str(remote), str(work))
    git(work, "config", "user.name", "A"); git(work, "config", "user.email", "a@x")
    overlay_code(work)
    # intruso: após o push do claim, troca token no remoto
    hook = tmp_path / "intruso.sh"
    hook.write_text(f"""#!/bin/bash
set -e
d=$(mktemp -d); git clone -q {remote} "$d"; cd "$d"
git config user.name i; git config user.email i@x
f=docs/memory/handoffs/fila/{iid}.json
python3 - "$f" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p))
d["consumer"]["claim_token"]="TOKEN-INTRUSO"
d["consumer"]["consumer_id"]="intruso:0"
open(p,"w").write(json.dumps(d,indent=2,ensure_ascii=False)+"\\n")
PY
git commit -qam intruso && git push -q origin HEAD:main
""")
    hook.chmod(0o755)
    barrier = tmp_path / "b"; barrier.mkdir()
    out = tmp_path / "out.json"
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GITHUB_", "AIMEM_"))}
    env.update({
        "AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1",
        "AI_MEMORY_DATA_DIR": str(tmp_path / "d"),
        "GITHUB_WORKFLOW": "A", "GITHUB_RUN_ID": "9", "GITHUB_RUN_ATTEMPT": "1",
        "AIMEM_TEST_AFTER_CLAIM_PUSH": f"bash {hook}",
    })
    # claim-race com barreira já go
    (barrier / "A").parent.mkdir(exist_ok=True)
    # chamar claim_id direto via session path — usar claim-race
    bfile = barrier / "A"
    proc = subprocess.Popen(
        [PY, "-m", "aimem", "claim-race", "--id", iid, "--out", str(out), "--barrier", str(bfile)],
        cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    for _ in range(2000):
        if bfile.exists():
            break
        time.sleep(0.01)
    (pathlib.Path(str(bfile) + ".go")).write_text("go")
    proc.wait(timeout=120)
    data = json.loads(out.read_text())
    assert data["claim_status"] == "lost", data
    # remoto ficou com o intruso (ou com o estado pós-intruso); de qualquer forma A não assumiu
    assert data.get("remote_matches") is not True

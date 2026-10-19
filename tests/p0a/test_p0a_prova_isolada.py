"""D2 — itens de PROVA nunca viram memória válida para um consumidor real.

Mecanismo (aimem/ledger.py): marcação estrutural `kind: "prova"` + `prova: {workflow, run_id, run_attempt}` em
todo item criado dentro do workflow de prova; itens legados sem `kind` são reconhecidos pela origem
(`origin.workflow` ∈ PROVA_WORKFLOWS). `_claimable` e o CAS de `claim_one`/`claim_id` recusam item de prova a
qualquer consumidor que não seja o próprio run de prova. O `seed` não carrega páginas de sessão de prova
no servidor (briefing). Fixtures = bytes reais de p0a @ 19de0b7, lidos do objeto git do histórico (sha256
conferidos; sem cópia no repo). Precisa de histórico completo (ci.yml: fetch-depth 0); ausência = falha, não skip.
"""
from __future__ import annotations

import hashlib, json, pathlib, re, subprocess

import pytest

from tests.p0a.fakeserver import FakeAIMemory
from tests.p0a.helpers import CODE, HIST, PY, Job, git, make_remote, remote_tree, synthetic_memory

P0A_19DE0B7 = "19de0b7df02567eec023334322649500f4c946d9"   # p0a-fila-handoffs publicado (estado remoto real)
FILA = "docs/memory/handoffs/fila"
PROVA_B_LEGADO = f"{FILA}/20261019T023307Z-39190430768-1-04d891.json"           # pending, "[prova-B]…"
LEGIT = f"{FILA}/20261018T234221Z-39177110784-1-e49f682ec9e6.json"               # pending, er-toolcheck
LEGIT_SUMMARY = "[toolcheck] er-toolcheck concluiu em 141s"
MD_AMBIG = ["docs/memory/handoffs/2026-10-19-prova-b-277e23.md", "docs/memory/sessoes/2026-10-19-prova-b-277e23.md"]
SESS_LEGIT = "docs/memory/sessoes/2026-10-18-toolcheck-82b631.md"
SHA_FIX = {
    "handoffs/2026-10-19-prova-b-277e23.md": "6451bbaed05d13ca755104e7af3da43bf9df34d38b6ca1230b75ea84d1e8f9d7",
    "handoffs/fila/20261018T234221Z-39177110784-1-e49f682ec9e6.json": "90257fe04f13833cc68b8359744157f41b6c6cbce2a8384990bfccdb60e3f02f",
    "handoffs/fila/20261019T023307Z-39190430768-1-04d891.json": "5395c07a5273e9402bd4005cf5c2063fb6aceca6136817e442c153e180684711",
    "sessoes/2026-10-18-toolcheck-82b631.md": "56faa1c41c5279c1a39dca64218e47f3c848a9156d4b0acf7bba11ab5ebc3d63",
    "sessoes/2026-10-19-prova-b-277e23.md": "e564c5d455a99d0f9b373e74e624d1cc3b67481f9ec1ce6c3dd9359d31cb1825",
}
PROVA_RUN, OUTRO_RUN_PROVA = 901, 902


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _fix(rel: str) -> bytes:
    r = subprocess.run(["git", "show", f"{P0A_19DE0B7}:docs/memory/{rel}"], cwd=HIST, capture_output=True)
    if r.returncode:
        pytest.fail(f"objeto {P0A_19DE0B7[:7]}:{rel} ausente em {HIST} (precisa de histórico completo): {r.stderr[-200:]!r}")
    return r.stdout


def test_fixtures_sao_os_bytes_reais_de_p0a():
    for rel, h in SHA_FIX.items():
        assert _sha(_fix(rel)) == h, rel


def _memoria(tmp, *, legit=True, aberto=False) -> pathlib.Path:
    mem = synthetic_memory(tmp / "mem-src")
    if not aberto:
        (mem / "handoffs" / "aberto.json").unlink()
    for rel in SHA_FIX:
        if not legit and rel.startswith("handoffs/fila/20261018T234221Z"):
            continue
        dst = mem / rel; dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(_fix(rel))
    return mem


def _tree(remote) -> dict:
    out = {}
    for line in git(remote, "ls-tree", "-r", "-z", "main", "--", "docs/memory").split("\0"):
        if not line:
            continue
        meta, path = line.split("\t", 1)
        out[path] = meta.split()[2]
    return out


def _blob(remote, path) -> dict:
    return json.loads(git(remote, "show", f"main:{path}"))


def _prova_a(tmp, remote, srv, run=PROVA_RUN):
    a = Job(tmp, remote, f"a{run}", run_id=run, server=srv, workflow="er-memory-persist", extra_env={"GITHUB_JOB": "job-a"})
    out = tmp / f"gho-{run}"
    r = a.run(PY, "-m", "aimem", "prova-item", "--summary", "prova persistência job A→B (conteúdo conhecido)",
              "--next", "job-B deve consumir", "--github-output", str(out))
    assert r.returncode == 0, r.stderr
    assert a.commit("er-memory-persist-A").returncode == 0
    kv = dict(l.split("=", 1) for l in out.read_text().splitlines())
    return kv["handoff_id"], kv["handoff_sha256"]


def _session_rec(job) -> dict:
    p = job.dir / "out" / "aimem" / f"session-ag-{job.name.lower()}.json"
    return json.loads(p.read_text()) if p.is_file() else {}


# ------------------------------------------------------------------ consumidor real: fila mista
def test_consumidor_real_recebe_so_o_legitimo_e_prova_fica_intacta(tmp_path):
    remote = make_remote(tmp_path, memory_from=_memoria(tmp_path))
    srv = FakeAIMemory(tmp_path / "srv")
    try:
        hid, _ = _prova_a(tmp_path, remote, srv)                       # prova nova (kind=prova), run 901
        prova_paths = [PROVA_B_LEGADO, f"{FILA}/{hid}.json", *MD_AMBIG]
        antes = _tree(remote)
        # er-toolcheck (claim normal, sem AIMEM_CLAIM_ID)
        c = Job(tmp_path, remote, "toolcheck", run_id=300, server=srv, workflow="er-toolcheck")
        assert c.seed().returncode == 0
        assert c.session(label="toolcheck").returncode == 0, c.last.stderr[-600:]
        assert c.received() == LEGIT_SUMMARY
        assert _session_rec(c)["handoff_claimed_id"] == pathlib.Path(LEGIT).stem
        assert c.commit("toolcheck").returncode == 0
        depois = _tree(remote)
        for p in prova_paths:                                          # prova byte a byte intacta
            assert depois[p] == antes[p], p
        assert _blob(remote, LEGIT)["state"] == "consumed"
        assert _blob(remote, LEGIT)["consumed"]["consumer_id"] == "er-toolcheck:300"
        # segundo consumidor real (er-analyze): só sobram itens de prova + o novo item legítimo do toolcheck
        novos_legit = [p for p in depois if p.startswith(FILA) and p not in antes and not _blob(remote, p).get("kind")]
        assert len(novos_legit) == 1
        d = Job(tmp_path, remote, "analyze", run_id=301, server=srv, workflow="er-analyze")
        assert d.session(label="analyze").returncode == 0, d.last.stderr[-600:]
        assert _session_rec(d)["handoff_claimed_id"] == pathlib.Path(novos_legit[0]).stem   # nunca a prova
        for p in prova_paths:
            assert _tree(remote)[p] == antes[p], p
    finally:
        srv.close()


def test_so_itens_de_prova_consumidor_real_nao_recebe_nada(tmp_path):
    remote = make_remote(tmp_path, memory_from=_memoria(tmp_path, legit=False))
    srv = FakeAIMemory(tmp_path / "srv")
    try:
        hid, _ = _prova_a(tmp_path, remote, srv)
        antes = _tree(remote)
        for wf, run in (("er-toolcheck", 310), ("er-analyze", 311), ("er-harness", 312)):
            c = Job(tmp_path, remote, f"c{run}", run_id=run, server=srv, workflow=wf)
            assert c.session(label="x").returncode == 0, c.last.stderr[-600:]
            rec = _session_rec(c)
            assert rec["handoff_received"] is None and rec["handoff_claimed_id"] is None, rec
        depois = _tree(remote)
        for p in (PROVA_B_LEGADO, f"{FILA}/{hid}.json", *MD_AMBIG):
            assert depois[p] == antes[p], p
        assert _blob(remote, PROVA_B_LEGADO)["state"] == "pending"
    finally:
        srv.close()


@pytest.mark.parametrize("alvo", ["legado", "novo"])
def test_claim_explicito_de_prova_por_consumidor_real_e_recusado(tmp_path, alvo):
    remote = make_remote(tmp_path, memory_from=_memoria(tmp_path, legit=False))
    srv = FakeAIMemory(tmp_path / "srv")
    try:
        hid, _ = _prova_a(tmp_path, remote, srv)
        iid = pathlib.Path(PROVA_B_LEGADO).stem if alvo == "legado" else hid
        antes = _tree(remote)
        c = Job(tmp_path, remote, "real", run_id=320, server=srv, workflow="er-toolcheck",
                extra_env={"AIMEM_CLAIM_ID": iid})
        r = c.session(label="x")
        assert r.returncode == 0
        assert '"claim_status": "lost"' in r.stdout and "PROVA" in r.stdout, r.stdout[-400:]
        assert _tree(remote) == antes                                   # nada mudou no remoto
    finally:
        srv.close()


def test_outro_run_de_prova_nao_consome_prova_alheia(tmp_path):
    remote = make_remote(tmp_path, memory_from=_memoria(tmp_path, legit=False))
    srv = FakeAIMemory(tmp_path / "srv")
    try:
        hid, _ = _prova_a(tmp_path, remote, srv, run=PROVA_RUN)
        antes = _tree(remote)
        o = Job(tmp_path, remote, "outra", run_id=OUTRO_RUN_PROVA, server=srv, workflow="er-memory-persist")
        assert o.session(label="x").returncode == 0
        assert _session_rec(o)["handoff_claimed_id"] is None
        o2 = Job(tmp_path, remote, "outra2", run_id=OUTRO_RUN_PROVA, server=srv, workflow="er-memory-persist",
                 extra_env={"AIMEM_CLAIM_ID": hid})
        r = o2.session(label="y")
        assert '"claim_status": "lost"' in r.stdout, r.stdout[-300:]
        for p in (PROVA_B_LEGADO, f"{FILA}/{hid}.json"):
            assert _tree(remote)[p] == antes[p]
    finally:
        srv.close()


# ------------------------------------------------------------------ o próprio fluxo de prova A→B continua
def test_fluxo_de_prova_A_B_continua_e_saida_de_B_e_prova(tmp_path):
    remote = make_remote(tmp_path, memory_from=_memoria(tmp_path, legit=False))
    srv = FakeAIMemory(tmp_path / "srv")
    try:
        hid, sha = _prova_a(tmp_path, remote, srv)
        raw = git(remote, "show", f"main:{FILA}/{hid}.json") + "\n"
        assert _sha(raw.encode()) == sha                                # sha do output == bytes publicados
        it = json.loads(raw)
        assert it["kind"] == "prova" and it["prova"] == {"workflow": "er-memory-persist", "run_id": str(PROVA_RUN),
                                                           "run_attempt": "1"}
        antes = set(_tree(remote))
        b = Job(tmp_path, remote, "b", run_id=PROVA_RUN, server=srv, workflow="er-memory-persist",
                extra_env={"GITHUB_JOB": "job-b", "AIMEM_CLAIM_ID": hid})
        b.seed()
        r = b.run(PY, "-m", "aimem", "session", "--agent", "er-memory-persist", "--label", "prova-B", "--", "true")
        assert r.returncode == 0, r.stderr[-600:]
        assert b.commit("er-memory-persist-B").returncode == 0
        a_item = _blob(remote, f"{FILA}/{hid}.json")
        assert a_item["state"] == "consumed" and a_item["consumed"]["consumer_id"] == f"er-memory-persist:{PROVA_RUN}"
        novos = sorted(set(_tree(remote)) - antes)
        fila_b = [p for p in novos if p.startswith(FILA + "/")]
        assert len(fila_b) == 1
        item_b = _blob(remote, fila_b[0])
        assert item_b["kind"] == "prova" and item_b["state"] == "pending" and "[prova-B]" in item_b["summary"]
        sess_b = [p for p in novos if p.startswith("docs/memory/sessoes/")]
        assert len(sess_b) == 1 and "- tipo: prova" in git(remote, "show", f"main:{sess_b[0]}")
        # consumidor real depois do run de prova: não recebe nada (só prova na fila) e o seed não carrega prova
        srv2 = FakeAIMemory(tmp_path / "srv2")
        try:
            c = Job(tmp_path, remote, "real", run_id=330, server=srv2, workflow="er-toolcheck")
            s = c.seed(); assert s.returncode == 0, s.stderr
            out = json.loads(s.stdout.splitlines()[-1])
            assert out["pending_handoffs"] == []
            semeadas = {a["path"] for n, a in srv2.calls if n == "memory_write_page"}
            assert f"sessoes/{pathlib.Path(sess_b[0]).name}" not in semeadas
            assert "sessoes/2026-10-19-prova-b-277e23.md" not in semeadas
            assert "sessoes/2026-10-18-toolcheck-82b631.md" in semeadas         # legítima continua
            assert c.session(label="x").returncode == 0
            assert _session_rec(c)["handoff_claimed_id"] is None
        finally:
            srv2.close()
    finally:
        srv.close()


def test_seed_nao_carrega_sessao_de_prova_legada_mas_carrega_legitima(tmp_path):
    remote = make_remote(tmp_path, memory_from=_memoria(tmp_path))
    srv = FakeAIMemory(tmp_path / "srv")
    try:
        c = Job(tmp_path, remote, "seed", run_id=340, server=srv, workflow="er-toolcheck")
        s = c.seed(); assert s.returncode == 0, s.stderr
        semeadas = {a["path"] for n, a in srv.calls if n == "memory_write_page"}
        assert "sessoes/2026-10-18-toolcheck-82b631.md" in semeadas
        assert "sessoes/2026-10-19-prova-b-277e23.md" not in semeadas
        pend = json.loads(s.stdout.splitlines()[-1])["pending_handoffs"]
        assert pend == [pathlib.Path(LEGIT).stem]                                     # prova-B legado fora
        assert git(c.dir, "status", "--porcelain") == ""                              # seed não altera arquivos
    finally:
        srv.close()


def test_migracao_dentro_do_workflow_de_prova_nao_marca_item_legitimo(tmp_path):
    remote = make_remote(tmp_path, memory_from=_memoria(tmp_path, legit=False, aberto=True))
    j = Job(tmp_path, remote, "pre", run_id=PROVA_RUN, workflow="er-memory-persist")
    assert j.run(PY, "-m", "aimem", "migrate", "--by", "er-memory-persist-pre").returncode == 0
    items = json.loads(j.run(PY, "-m", "aimem", "fila", "--json").stdout)
    mig = [i for i in items if i.get("migration")]
    assert len(mig) == 1 and "kind" not in mig[0] and mig[0]["origin"]["workflow"] == "fyah-tools"


# ------------------------------------------------------------------ unidades
def _ledger():
    import sys
    sys.path.insert(0, str(CODE))
    from aimem import ledger
    return ledger


def test_unidade_recusa_prova(monkeypatch):
    ledger = _ledger()
    legado = json.loads(_fix("handoffs/fila/20261019T023307Z-39190430768-1-04d891.json"))
    legit = json.loads(_fix("handoffs/fila/20261018T234221Z-39177110784-1-e49f682ec9e6.json"))
    assert ledger.is_prova(legado) and not ledger.is_prova(legit)
    for wf, rid, recusa in (("er-toolcheck", "39190430768", True), ("er-memory-persist", "1", True),
                            ("er-memory-persist", "39190430768", False), ("local", "local", True)):
        m = {"workflow": wf, "run_id": rid, "consumer_id": f"{wf}:{rid}", "attempt_id": f"{rid}.1", "run_attempt": "1"}
        assert bool(ledger.recusa_prova(legado, m)) is recusa, (wf, rid)
        assert ledger._claimable(legado, m)[0] is (not recusa)
        assert ledger.recusa_prova(legit, m) is None


def test_merge_nao_descarta_marcacao_de_prova():
    ledger = _ledger()
    a = json.loads(_fix("handoffs/fila/20261019T023307Z-39190430768-1-04d891.json"))
    b = json.loads(json.dumps(a)); b["kind"] = "prova"; b["prova"] = {"workflow": "er-memory-persist", "run_id": "1", "run_attempt": "1"}
    with pytest.raises(ledger.UnsafeMerge):
        ledger.merge_items(a, b)


def test_nenhum_codigo_le_handoffs_md():
    """Os .md de handoffs/ (incl. o prova-b ambíguo) são só leitura humana: nada no aimem os lê."""
    for f in (CODE / "aimem").glob("*.py"):
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if '"handoffs"' in line and re.search(r"glob\(|read_text|read_bytes|open\(", line):
                assert ".md" not in line, f"{f.name}:{n}: {line.strip()}"

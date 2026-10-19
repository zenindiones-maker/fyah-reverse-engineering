"""P0a — regressão de integridade da memória/handoff (issue #3).

Cada teste reproduz uma falha encontrada no DIAGNOSTICO.md. Eles foram escritos ANTES
da correção e devem FALHAR contra o código atual (main 4ffade0).
Infra: remoto bare + clones independentes (um por "job"), servidor ai-memory falso
por job (ou nenhum = degradado). Sem rede.
"""
from __future__ import annotations

import hashlib, json, os, pathlib, subprocess, sys, time

import pytest

from tests.p0a.fakeserver import FakeAIMemory
from tests.p0a.helpers import CODE, HIST, PY, Job, fila, git, make_remote, overlay_code, remote_file, remote_tree

P = "[audio-full] fyah-tools concluiu em 5s; schema fyah-re/audio-full@1"   # handoff aberto em 4ffade0
LOST_COMMIT, OVERWRITE_COMMIT = "4a0ec59", "4ffade0"
LOST_STEP = "Consertar o que aparecer como falha em docs/ferramentas/STATUS.md"


@pytest.fixture
def env(tmp_path):
    servers = []

    def srv(**kw):
        s = FakeAIMemory(tmp_path / f"srv{len(servers)}", **kw); servers.append(s); return s

    remote = make_remote(tmp_path)
    yield tmp_path, remote, srv
    for s in servers:
        s.close()


def job(tmp, remote, name, run_id, srv=None, **kw):
    j = Job(tmp, remote, name, run_id=run_id, server=srv() if srv else None, **kw)
    j.seed()
    return j


# ---------------------------------------------------------------- F1: -X theirs
def test_F1_x_theirs_nao_perde_handoff_concorrente(env):
    """Dois jobs concorrentes deixam handoffs; os DOIS têm de ser entregues depois (nenhum sobrescrito)."""
    tmp, remote, srv = env
    a = job(tmp, remote, "A", 101, srv); b = job(tmp, remote, "B", 102, srv)
    assert a.session(label="job-A").returncode == 0
    assert b.session(label="job-B").returncode == 0
    assert a.commit().returncode == 0
    assert b.commit().returncode == 0
    got = set()
    for i, n in enumerate(("C", "D")):
        j = job(tmp, remote, n, 200 + i, srv); j.session(); got.add(j.received()); j.commit()
    want = {s for s in got if s and ("[job-A]" in s or "[job-B]" in s)}
    assert len(want) == 2, f"handoff perdido: C/D receberam {got}"


def test_F1b_conflito_fora_da_fila_falha_e_preserva(env):
    """Conflito em arquivo autorizado não-JSON: nada de -X theirs; exit!=0, remoto intacto, patch+bundle."""
    tmp, remote, srv = env
    a = job(tmp, remote, "A", 111, srv, extra_env={"AIMEM_SYNC_EXTRA": "docs/ferramentas/STATUS.md"})
    a.session(); assert a.commit().returncode == 0   # sync limpo da memória
    other = Job(tmp, remote, "outro", run_id=112)
    (other.dir / "docs/ferramentas/STATUS.md").write_text("status do OUTRO run\n")
    git(other.dir, "commit", "-qam", "outro"); git(other.dir, "push", "-q", "origin", "HEAD:main")
    # A altera STATUS a partir do ancestral comum (ainda não fetched o outro) → conflito no rebase
    (a.dir / "docs/ferramentas/STATUS.md").write_text("status do run A\n")
    r = a.commit()
    assert r.returncode != 0, f"conflito tratado como sucesso: {r.stdout}{r.stderr}"
    assert remote_file(tmp, remote, "docs/ferramentas/STATUS.md") == b"status do OUTRO run\n"
    d = a.dir / "out" / "aimem" / "conflito"
    patches, bundles = list(d.rglob("*.patch")), list(d.rglob("*.bundle"))
    assert patches and bundles, "dados do job não preservados como artefato"
    assert "status do run A" in "".join(p.read_text() for p in patches)
    assert git(a.dir, "bundle", "verify", str(bundles[0]), check=False) is not None
    sh = (CODE / "scripts" / "aimem_commit.sh").read_text()
    assert "pull --rebase -X" not in sh and "-X theirs" not in sh.replace("estratégia theirs", "")


# ---------------------------------------------------------------- F2: handoff duplo
def test_F2_dois_jobs_nao_consomem_o_mesmo_handoff(env):
    tmp, remote, srv = env
    a = job(tmp, remote, "A", 121, srv); b = job(tmp, remote, "B", 122, srv)   # mesmo SHA
    a.session(); b.session()
    rec = [a.received(), b.received()]
    assert sum(1 for x in rec if x == P) == 1, f"handoff entregue {rec.count(P)}x: {rec}"


def test_F2b_validacao_remota_apos_push(env, tmp_path):
    """Após o push do claim, outro escritor troca o claim no remoto: o job tem de refazer o fetch,
    perceber que o claim gravado não é o dele e NÃO entregar o handoff."""
    tmp, remote, srv = env
    hook = tmp_path / "intruso.sh"
    hook.write_text(f"""set -e
d=$(mktemp -d); git clone -q {remote} $d; cd $d; git config user.name i; git config user.email i@x
for f in docs/memory/handoffs/fila/*.json; do
  python3 - "$f" <<'PY'
import json,sys; p=sys.argv[1]; d=json.load(open(p))
if d.get("state")=="claimed":
    d["consumer"]["claim_token"]="TOKEN-DO-INTRUSO"; d["consumer"]["consumer_id"]="intruso:999"
    open(p,"w").write(json.dumps(d,indent=2,ensure_ascii=False)+"\\n")
PY
done
git commit -qam intruso && git push -q origin HEAD:main
""")
    a = job(tmp, remote, "A", 131, srv, extra_env={"AIMEM_TEST_AFTER_CLAIM_PUSH": f"bash {hook}"})
    a.session()
    assert a.received() != P, "claim não validado no remoto após o push"


# ---------------------------------------------------------------- F3: _persist sobrescreve
def test_F3_servidor_fora_nao_sobrescreve_pendente(env):
    tmp, remote, srv = env
    x = job(tmp, remote, "X", 141)               # degradado: sem servidor
    assert x.session(label="degradado").returncode == 0
    assert x.commit().returncode == 0
    y = job(tmp, remote, "Y", 142, srv); y.session(); y.commit()
    assert y.received() == P, f"pendente perdido com servidor fora; Y recebeu {y.received()!r}"


def test_F3b_rc_falha_nao_sobrescreve_e_devolve(env):
    tmp, remote, srv = env
    f = job(tmp, remote, "F", 151, srv)
    assert f.session("sh", "-c", "exit 3", label="falha").returncode == 3
    f.commit()
    g = job(tmp, remote, "G", 152, srv); g.session(); g.commit()
    assert g.received() == P, f"handoff não devolvido após falha; G recebeu {g.received()!r}"


def test_F3c_falhas_repetidas_viram_failed_visivel(env):
    tmp, remote, srv = env
    for i in range(3):
        f = job(tmp, remote, f"F{i}", 160 + i, srv); f.session("sh", "-c", "exit 3"); f.commit()
    z = job(tmp, remote, "Z", 169, srv)
    item = [it for it in fila(z) if it["summary"] == P]
    assert item and item[0]["state"] == "failed" and item[0]["attempts"] == 3
    z.session()
    assert z.received() != P


def test_F3d_sessao_nao_reescreve_aberto_json(env):
    tmp, remote, srv = env
    before = remote_file(tmp, remote, "docs/memory/handoffs/aberto.json")
    a = job(tmp, remote, "A", 171, srv); a.session(); a.commit()
    assert remote_file(tmp, remote, "docs/memory/handoffs/aberto.json") == before


# ---------------------------------------------------------------- F4: accept sem ID
def test_F4_accept_sem_id_nao_pega_handoff_alheio(env):
    tmp, remote, srv = env
    s = srv(reject_accept_by_id=True, preload_open=["INTRUSO de outra sessão"])
    j = Job(tmp, remote, "A", run_id=181, server=s); j.seed(); j.session()
    assert j.received() != "INTRUSO de outra sessão", "fallback accept() sem ID pegou handoff alheio"
    assert not any(n == "memory_handoff_accept" and "handoff_id" not in a for n, a in s.calls)


# ---------------------------------------------------------------- F5: client.py:86
def test_F5_resposta_nao_json_vira_AIMemoryError(tmp_path, monkeypatch):
    sys.path.insert(0, str(CODE))
    for m in [m for m in sys.modules if m == "aimem" or m.startswith("aimem.")]:
        del sys.modules[m]
    from aimem.client import AIMemoryError, Client
    s = FakeAIMemory(tmp_path / "s", nonjson=True)
    try:
        with pytest.raises(AIMemoryError):
            Client(url=s.url).mcp("memory_query", query="x")
    finally:
        s.close(); sys.path.remove(str(CODE))


# ---------------------------------------------------------------- F6: commit sai 0 em falha
def test_F6_commit_falha_sai_nao_zero_e_preserva(env):
    tmp, remote, srv = env
    a = job(tmp, remote, "A", 191, srv); a.session()
    hook = pathlib.Path(remote) / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho recusado >&2\nexit 1\n"); hook.chmod(0o755)
    t0 = time.time(); r = a.commit()
    assert r.returncode != 0, "falha ao salvar memória terminou com exit 0"
    assert time.time() - t0 < 30, "retry sem limite/backoff configurável"
    d = a.dir / "out" / "aimem" / "conflito"
    bundles = list(d.rglob("*.bundle"))
    assert bundles and list(d.rglob("*.patch"))
    heads = git(a.dir, "bundle", "list-heads", str(bundles[0]))
    assert git(a.dir, "rev-parse", "HEAD") in heads


# ---------------------------------------------------------------- F7: só caminhos autorizados
def test_F7_preserva_nao_relacionados_e_so_commita_autorizado(env):
    tmp, remote, srv = env
    a = job(tmp, remote, "A", 201, srv)
    luiz = Job(tmp, remote, "luiz", run_id=202)
    (luiz.dir / "README.md").write_text("editado pelo Luiz\n")
    (luiz.dir / "docs/memory/paginas/hierarquia.md").write_text("hierarquia nova do Luiz\n")
    git(luiz.dir, "commit", "-qam", "luiz"); git(luiz.dir, "push", "-q", "origin", "HEAD:main")
    a.session()
    regras_orig = (a.dir / "docs/memory/paginas/regras.md").read_bytes()
    (a.dir / "docs/memory/paginas/regras.md").write_text("subordinado reescreveu as regras\n")  # envenenamento
    (a.dir / "out").mkdir(exist_ok=True); (a.dir / "out" / "x.json").write_text("{}")
    (a.dir / "docs/ferramentas/STATUS.md").write_text("status local não autorizado\n")
    assert a.commit().returncode == 0
    t = remote_tree(tmp, remote)
    assert (t / "README.md").read_text() == "editado pelo Luiz\n"
    assert (t / "docs/memory/paginas/hierarquia.md").read_text() == "hierarquia nova do Luiz\n"
    assert (t / "docs/memory/paginas/regras.md").read_bytes() == regras_orig, "commitou paginas/ alterada pelo subordinado"
    assert (t / "docs/ferramentas/STATUS.md").read_text() == "status base\n"
    assert not (t / "out" / "x.json").exists()
    assert list((t / "docs/memory/sessoes").glob("*job-a*.md")), "sessão do job não foi salva"


# ---------------------------------------------------------------- F8: retry / lease
def test_F8_retry_mesmo_run_assume_claim_outro_run_nao(env):
    tmp, remote, srv = env
    k1 = job(tmp, remote, "K", 211, srv)
    k1.session("sh", "-c", "kill -9 $PPID")            # job morre depois do claim, sem confirmar
    other = job(tmp, remote, "O", 212, srv); other.session()
    assert other.received() != P, "outro run pegou handoff com claim/lease válido"
    k2 = Job(tmp, remote, "K", run_id=211, attempt=2, server=srv()); k2.seed(); k2.session(); k2.commit()
    assert k2.received() == P, "re-run (attempt 2) do mesmo run não retomou o próprio claim"
    it = [i for i in fila(k2) if i["summary"] == P][0]
    assert it["state"] == "consumed"
    assert sum(1 for h in it["history"] if h["to"] == "consumed") == 1
    assert any("retry" in (h.get("reason") or "") for h in it["history"])


def test_F8b_lease_expirado_reclaim_registrado(env):
    tmp, remote, srv = env
    k = job(tmp, remote, "K", 221, srv, extra_env={"AIMEM_LEASE_SECONDS": "6"})
    k.session("sh", "-c", "kill -9 $PPID")
    m = job(tmp, remote, "M", 222, srv); m.session()
    assert m.received() != P, "reclaim antes do lease expirar"
    time.sleep(7)
    l = job(tmp, remote, "L", 223, srv); l.session(); l.commit()
    assert l.received() == P
    it = [i for i in fila(l) if i["summary"] == P][0]
    assert any("lease expirado" in (h.get("reason") or "") for h in it["history"])
    assert it["consumer"]["consumer_id"].endswith(":223")


def test_F8c_sync_idempotente(env):
    tmp, remote, srv = env
    a = job(tmp, remote, "A", 231, srv); a.session()
    assert a.commit().returncode == 0
    n = git(a.dir, "rev-list", "--count", "origin/main")
    r = a.commit()
    assert r.returncode == 0 and git(a.dir, "rev-list", "--count", "origin/main") == n
    it = [i for i in fila(a) if i["summary"] == P][0]
    assert [h["to"] for h in it["history"]].count("consumed") == 1


# ---------------------------------------------------------------- F9: formato do item
def test_F9_item_tem_id_origem_estado_consumidor_historico(env):
    tmp, remote, srv = env
    a = job(tmp, remote, "A", 241, srv, workflow="er-analyze"); a.session(label="job-A"); a.commit()
    items = fila(a)
    mine = [i for i in items if i["summary"].startswith("[job-A]")]
    assert len(mine) == 1
    i = mine[0]
    assert i["schema"] == "fyah-handoff@1" and i["state"] == "pending"
    o = i["origin"]
    assert o["workflow"] == "er-analyze" and o["run_id"] == "241" and o["sha"] and o["session"]
    assert len({x["id"] for x in items}) == len(items)
    consumed = [x for x in items if x["summary"] == P][0]
    c = consumed["consumer"]
    assert c["consumer_id"] == "er-analyze:241" and c["claim_token"] and c["attempt_id"] == "241.1"
    assert [h["to"] for h in consumed["history"]][-2:] == ["claimed", "consumed"]


# ---------------------------------------------------------------- F10: recuperação real
def test_recupera_handoff_perdido(tmp_path):
    """Reconstrói o cenário real: remoto com o histórico do repo (4a0ec59 → 4ffade0) e
    exige o handoff do toolcheck de volta na fila, byte a byte, com registro da recuperação."""
    remote = tmp_path / "origin.git"
    git(tmp_path, "clone", "-q", "--bare", str(HIST), str(remote))
    w = tmp_path / "w"; git(tmp_path, "clone", "-q", str(remote), str(w))
    git(w, "config", "user.name", "teste"); git(w, "config", "user.email", "t@x")
    git(w, "checkout", "-q", "-B", "main", OVERWRITE_COMMIT)
    original = subprocess.run(["git", "show", f"{LOST_COMMIT}:docs/memory/handoffs/aberto.json"],
                              cwd=w, capture_output=True, check=True).stdout
    assert LOST_STEP.encode() in original
    assert LOST_STEP.encode() not in (w / "docs/memory/handoffs/aberto.json").read_bytes()
    overlay_code(w); git(w, "add", "-A"); git(w, "commit", "-qm", "codigo sob teste", check=False)
    git(w, "push", "-q", "-f", "origin", "HEAD:main")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GITHUB_", "AIMEM_"))}
    env.update({"AIMEM_SYNC_BACKOFF": "0", "PYTHONDONTWRITEBYTECODE": "1", "AI_MEMORY_DATA_DIR": str(tmp_path / "d")})
    r = subprocess.run([PY, "-m", "aimem", "recover", "--commit", LOST_COMMIT, "--overwritten-by", OVERWRITE_COMMIT,
                        "--path", "docs/memory/handoffs/aberto.json", "--by", "E.R. (teste)"],
                       cwd=w, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-500:]
    assert subprocess.run(["bash", "scripts/aimem_commit.sh", "recuperacao"], cwd=w, env=env).returncode == 0
    # validação no REMOTO
    v = tmp_path / "v"; git(tmp_path, "clone", "-q", str(remote), str(v))
    items = [json.loads(p.read_text()) for p in sorted((v / "docs/memory/handoffs/fila").glob("*.json"))]
    rec = [i for i in items if (i.get("recovery") or {}).get("from_commit", "").startswith(LOST_COMMIT)]
    assert len(rec) == 1, "handoff perdido não está na fila"
    it = rec[0]
    raw = (v / it["recovery"]["raw_path"]).read_bytes()
    assert raw == original, "conteúdo recuperado não é idêntico byte a byte"
    assert it["recovery"]["original_sha256"] == hashlib.sha256(original).hexdigest()
    orig = json.loads(original)
    for k in ("summary", "next_steps", "open_questions", "files_touched"):
        assert it[k] == orig[k]
    assert it["state"] == "pending"
    rv = it["recovery"]
    assert rv["overwritten_by_commit"].startswith(OVERWRITE_COMMIT)
    assert rv["source_run"].endswith("/39177110784") and rv["recovered_by"] == "E.R. (teste)" and rv["recovered_utc"]
    assert it["origin"]["session"] == orig["from_session"] and it["origin"]["run_id"] == "39177110784"
    assert it["history"][0]["to"] == "pending" and "recuper" in it["history"][0]["reason"]
    # idempotente: rodar de novo não duplica item nem transição espúria
    before_items = sorted(p.name for p in (w / "docs/memory/handoffs/fila").glob("*.json"))
    before_hist = len(json.loads((w / "docs/memory/handoffs/fila" / before_items[0]).read_text())["history"]) if len(before_items)==1 else None
    # se há mais de um (migrate+recover), achar o recuperado
    rec_path = next(p for p in (w / "docs/memory/handoffs/fila").glob("*.json")
                    if (json.loads(p.read_text()).get("recovery") or {}).get("from_commit", "").startswith(LOST_COMMIT))
    before_hist = len(json.loads(rec_path.read_text())["history"])
    before_sha = hashlib.sha256(rec_path.read_bytes()).hexdigest()
    subprocess.run([PY, "-m", "aimem", "recover", "--commit", LOST_COMMIT, "--overwritten-by", OVERWRITE_COMMIT,
                    "--path", "docs/memory/handoffs/aberto.json", "--by", "E.R. (teste)"], cwd=w, env=env, check=True,
                   capture_output=True)
    after_items = sorted(p.name for p in (w / "docs/memory/handoffs/fila").glob("*.json"))
    assert after_items == before_items
    assert len(json.loads(rec_path.read_text())["history"]) == before_hist
    assert hashlib.sha256(rec_path.read_bytes()).hexdigest() == before_sha
    assert git(w, "status", "--porcelain", "docs/memory") == ""
    # e é entregue (FIFO por created_utc: 23:42:21Z vem antes do [audio-full] 23:48:05Z)
    s = FakeAIMemory(tmp_path / "d2")
    try:
        e2 = dict(env, AI_MEMORY_SERVER_URL=s.url, GITHUB_RUN_ID="999", GITHUB_RUN_ATTEMPT="1", GITHUB_WORKFLOW="t",
                  AI_MEMORY_DATA_DIR=str(tmp_path / "d2"))
        subprocess.run([PY, "-m", "aimem", "session", "--agent", "ag-n", "--label", "n", "--", "true"], cwd=w, env=e2,
                       capture_output=True, check=True)
        got = json.loads((w / "out/aimem/session-ag-n.json").read_text())["handoff_received"]
        assert got == orig["summary"]
    finally:
        s.close()


def test_migracao_aberto_json_legado(env):
    tmp, remote, srv = env
    a = job(tmp, remote, "A", 251, srv)
    raw = (a.dir / "docs/memory/handoffs/aberto.json").read_bytes()
    r = a.run(PY, "-m", "aimem", "migrate"); assert r.returncode == 0, r.stderr[-300:]
    r2 = a.run(PY, "-m", "aimem", "migrate"); assert r2.returncode == 0
    items = [i for i in fila(a) if (i.get("migration") or {}).get("original_sha256")]
    assert len(items) == 1
    it = items[0]
    assert (a.dir / it["migration"]["raw_path"]).read_bytes() == raw
    assert it["summary"] == P and it["state"] == "pending"
    assert it["origin"]["session"] == json.loads(raw)["from_session"]

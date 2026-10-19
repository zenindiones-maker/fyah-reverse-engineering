"""C v2 — limpeza da prova por MANIFESTO autorizado + proveniência git (sem regra por nome).

Cenário: remoto bare + clones (um por "job"), como no Actions. O run simulado R cria os itens
de prova (job-a/job-b, commits com trailers Aimem-*), registra o manifesto e o job-c limpa.
Negativos: cada um prova que NENHUMA exclusão ocorreu (árvores local e remota iguais, sha256).
"""
from __future__ import annotations

import hashlib, json, os, pathlib, re, shutil, subprocess

import pytest

from tests.p0a.fakeserver import FakeAIMemory
from tests.p0a.helpers import CODE, PY, Job, fila, git, make_remote

SCRIPT = str(CODE / "scripts" / "aimem_limpa_prova.py")
WF, R, OTHER_RUN = "er-memory-persist", 901, 555
HID = f"persist-prova-a-{R}-1"
FILA = "docs/memory/handoffs/fila"
AMBIG = ["docs/memory/handoffs/2026-10-19-prova-b-277e23.md", "docs/memory/sessoes/2026-10-19-prova-b-277e23.md"]
LOOKALIKE = f"{FILA}/lookalike-prova-a.json"          # id/origin iguais aos da prova, NÃO criado pelo run
PROVA_B_OUTRO_DIA = "docs/memory/handoffs/2026-10-18-prova-b-aaaaaa.md"
RECUP = f"{FILA}/20261018T234221Z-39177110784-1-e49f682ec9e6.json"
RECUP_RAW = "docs/memory/handoffs/raw/recuperado-e49f682ec9e6.json"
SYMLINK = f"{FILA}/link-para-legit.json"
OTHER_RUN_FILE = f"{FILA}/criado-por-outro-run.json"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def tree_local(d: pathlib.Path) -> dict:
    out = {}
    for p in sorted((d / "docs/memory").rglob("*")):
        if p.is_symlink():
            out[str(p.relative_to(d))] = "symlink:" + os.readlink(p)
        elif p.is_file():
            out[str(p.relative_to(d))] = _sha(p.read_bytes())
    return out


def tree_remote(remote: pathlib.Path) -> dict:
    out = {}
    for line in git(remote, "ls-tree", "-r", "main", "--", "docs/memory").splitlines():
        meta, path = line.split("\t", 1)
        mode, _typ, obj = meta.split()
        blob = subprocess.run(["git", "cat-file", "blob", obj], cwd=remote, capture_output=True, check=True).stdout
        out[path] = f"{mode}:{_sha(blob)}"
    return out


def script(job, *args):
    return job.run(PY, SCRIPT, *args)


def _item(iid, *, workflow, run_id, attempt="1", session="s", summary=None, extra=None):
    now = "2026-10-19T00:00:00Z"
    d = {"schema": "fyah-handoff@1", "id": iid, "state": "pending", "summary": summary or f"item {iid}",
         "next_steps": [], "open_questions": [], "files_touched": [],
         "origin": {"workflow": workflow, "run_id": str(run_id), "run_attempt": attempt, "sha": None,
                    "session": session, "agent": workflow, "created_utc": now},
         "consumer": None, "consumed": None, "attempts": 0, "max_attempts": 3,
         "history": [{"at": now, "from": None, "to": "pending", "by": "t", "reason": "criado"}]}
    d.update(extra or {})
    return json.dumps(d, indent=2, ensure_ascii=False) + "\n"


def _human_commit(d: pathlib.Path, files: dict, msg: str, symlinks: dict | None = None):
    """Commit 'humano' (sem trailers Aimem-*) + push para main do remoto de teste."""
    for rel, content in files.items():
        p = d / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content)
    for rel, target in (symlinks or {}).items():
        p = d / rel; p.parent.mkdir(parents=True, exist_ok=True); os.symlink(target, p)
    git(d, "add", "-A", "docs/memory"); git(d, "commit", "-qm", msg); git(d, "push", "-q", "origin", "HEAD:main")


def _job(tmp, remote, name, run_id, job, srv=None, workflow=WF, extra=None):
    j = Job(tmp, remote, name, run_id=run_id, server=srv, workflow=workflow,
            extra_env={"GITHUB_JOB": job, **(extra or {})})
    git(j.dir, "fetch", "-q", "origin")
    return j


# ------------------------------------------------------------------ cenário (1 run simulado)
@pytest.fixture(scope="module")
def cenario(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("cenario")
    remote = make_remote(tmp)
    srv = FakeAIMemory(tmp / "srv")
    try:
        # estado prévio legítimo da branch
        setup = _job(tmp, remote, "setup", 100, "setup", srv, workflow="fyah-tools")
        assert setup.run(PY, "-m", "aimem", "migrate").returncode == 0
        cm = setup.commit("migra"); assert cm.returncode == 0, cm.stderr[-400:]   # migração + raw/aberto-*
        recup = _item("20261018T234221Z-39177110784-1-e49f682ec9e6", workflow="er-toolcheck", run_id=39177110784,
                      summary="[toolcheck] er-toolcheck concluiu em 141s",
                      extra={"recovery": {"from_commit": "4a0ec59", "overwritten_by_commit": "4ffade0"}})
        _human_commit(setup.dir, {
            RECUP: recup, RECUP_RAW: '{"summary": "original"}\n',
            AMBIG[0]: "# Handoff 2026-10-19 — prova-B\n", AMBIG[1]: "# sessão prova-B 277e23\n",
            PROVA_B_OUTRO_DIA: "# Handoff 2026-10-18 — prova-B (outro dia)\n",
            LOOKALIKE: _item(HID, workflow=WF, run_id=R, session="prova-a"),
        }, "estado prévio (humano)")
        prod = _job(tmp, remote, "toolcheck", 200, "toolcheck", srv, workflow="er-toolcheck")
        prod.seed()
        assert prod.session(label="legit").returncode == 0, prod.last.stderr[-400:]
        assert prod.commit("legit").returncode == 0
        legit = [i for i in fila(prod) if i["origin"]["workflow"] == "er-toolcheck" and not i.get("recovery")]
        assert len(legit) == 1, legit
        legit_path = f"{FILA}/{legit[0]['id']}.json"
        git(prod.dir, "pull", "-q", "--ff-only", "origin", "main")
        _human_commit(prod.dir, {}, "symlink (humano)", symlinks={SYMLINK: pathlib.Path(legit_path).name})
        pre_run = tree_remote(remote)

        # ---- job-a
        a = _job(tmp, remote, "a", R, "job-a", srv)
        run_base = git(a.dir, "rev-parse", "origin/main")
        assert script(a, "snapshot", "--ref", "origin/main", "--out", str(tmp / "antes-a.json")).returncode == 0
        (a.dir / FILA / f"{HID}.json").write_text(_item(HID, workflow=WF, run_id=R, session="prova-a",
                                                        summary="prova persistência job A→B"))
        ca = a.commit("er-memory-persist-A"); assert ca.returncode == 0, ca.stderr[-400:]
        git(a.dir, "fetch", "-q", "origin")
        ra = script(a, "registra", "--job", "job-a", "--run-base", run_base, "--antes", str(tmp / "antes-a.json"),
                    "--ref", "origin/main", "--out", str(tmp / "manifesto-a.json"))
        assert ra.returncode == 0, ra.stderr
        sha_a = json.loads(ra.stdout)["manifest_sha256"]

        # ---- job-b
        b = _job(tmp, remote, "b", R, "job-b", srv, extra={"AIMEM_CLAIM_ID": HID})
        assert script(b, "snapshot", "--ref", "origin/main", "--out", str(tmp / "antes-b.json")).returncode == 0
        b.seed()
        r = b.run(PY, "-m", "aimem", "session", "--agent", WF, "--label", "prova-B", "--", "true")
        assert r.returncode == 0, r.stderr[-400:]
        assert b.commit("er-memory-persist-B").returncode == 0
        # ---- outro run escreve DURANTE a janela do job-b (commit com trailers do run 555)
        o = _job(tmp, remote, "outro", OTHER_RUN, "job-b", srv)
        (o.dir / OTHER_RUN_FILE).write_text(_item("criado-por-outro-run", workflow=WF, run_id=OTHER_RUN))
        assert o.commit("outro-run").returncode == 0

        git(b.dir, "fetch", "-q", "origin")
        rb = script(b, "registra", "--job", "job-b", "--run-base", run_base, "--antes", str(tmp / "antes-b.json"),
                    "--ref", "origin/main", "--anterior", str(tmp / "manifesto-a.json"), "--anterior-sha256", sha_a,
                    "--out", str(tmp / "manifesto.json"))
        assert rb.returncode == 0, rb.stderr
        yield {"tmp": tmp, "remote": remote, "srv": srv, "run_base": run_base, "manifest": tmp / "manifesto.json",
               "sha": json.loads(rb.stdout)["manifest_sha256"], "pre_run": pre_run, "legit": legit[0],
               "legit_path": legit_path, "registra_b_stderr": rb.stderr, "post_b": tree_remote(remote)}
    finally:
        srv.close()


def _fresh(cen, tmp_path):
    """Cópia isolada do remoto + clone do job-c sincronizado."""
    remote = tmp_path / "remote.git"
    shutil.copytree(cen["remote"], remote, symlinks=True)
    return remote, _job(tmp_path, remote, "c", R, "job-c", cen["srv"])


def _manifest(cen) -> dict:
    return json.loads(cen["manifest"].read_bytes())


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _limpa(c, mpath, msha, run_base, *extra, confirmar=True):
    """Exclusão real = passo humano com --confirmar=<sha256 do manifesto> (D). Sem ele = dry-run."""
    conf = ("--confirmar", msha) if confirmar else ()
    r = script(c, "limpa", "--manifest", str(mpath), "--manifest-sha256", msha, "--run-base", run_base,
               "--ref", "origin/main", *conf, *extra)
    if r.returncode == 0:  # mesmo encadeamento do workflow (set -e): só commita se a limpeza passou
        assert c.commit("limpa").returncode == 0
    return r


def _assert_nada_apagado(remote, c, run, before_local, before_remote, esperado):
    assert run.returncode != 0, f"deveria abortar: {run.stdout}"
    assert "::error::" in run.stderr
    assert re.search(esperado, run.stderr), run.stderr
    assert json.loads(run.stdout.splitlines()[-1])["removidos"] == []
    assert tree_local(c.dir) == before_local, "árvore local mudou"
    assert tree_remote(remote) == before_remote, "árvore remota mudou"


# ------------------------------------------------------------------ positivo
def test_positivo_remove_so_manifesto_e_resto_byte_a_byte(cenario, tmp_path):
    m = _manifest(cenario)
    paths = {e["path"] for e in m["entries"]}
    # expectativa independente do script: criados no remoto durante o run, menos o do outro run
    criados = set(cenario["post_b"]) - set(cenario["pre_run"]) - {OTHER_RUN_FILE}
    assert paths == criados, paths ^ criados
    assert f"{FILA}/{HID}.json" in paths
    assert any(p.startswith("docs/memory/handoffs/efeitos/") for p in paths)
    assert any(p.startswith("docs/memory/sessoes/") for p in paths)
    assert any(p.startswith("docs/memory/handoffs/") and p.endswith(".md") for p in paths)
    assert OTHER_RUN_FILE in cenario["registra_b_stderr"]  # novo na janela, mas recusado no registro
    for e in m["entries"]:
        assert (e["workflow"], e["run_id"], e["run_attempt"]) == (WF, str(R), "1") and e["job"] in ("job-a", "job-b")

    remote, c = _fresh(cenario, tmp_path)
    antes_c = tmp_path / "antes-c.json"
    assert script(c, "snapshot", "--ref", "origin/main", "--out", str(antes_c)).returncode == 0
    before = tree_remote(remote)
    r = _limpa(c, cenario["manifest"], cenario["sha"], cenario["run_base"])
    assert r.returncode == 0, r.stderr
    assert set(json.loads(r.stdout)["removidos"]) == paths
    git(c.dir, "fetch", "-q", "origin")
    v = script(c, "verifica", "--antes", str(antes_c), "--manifest", str(cenario["manifest"]),
               "--manifest-sha256", cenario["sha"], "--ref", "origin/main")
    assert v.returncode == 0, v.stderr
    after = tree_remote(remote)
    assert after == {k: x for k, x in before.items() if k not in paths}
    for p in [RECUP, RECUP_RAW, *AMBIG, LOOKALIKE, PROVA_B_OUTRO_DIA, SYMLINK, cenario["legit_path"]]:
        assert after[p] == cenario["pre_run"][p], p          # byte a byte vs. ANTES do run
    raw_mig = [k for k in after if k.startswith("docs/memory/handoffs/raw/aberto-")]
    mig = [k for k in after if k.startswith(f"{FILA}/") and "39177105670" in k]
    assert raw_mig and mig and all(after[k] == cenario["pre_run"][k] for k in raw_mig + mig)
    assert after[OTHER_RUN_FILE] == cenario["post_b"][OTHER_RUN_FILE]

    # persistência legítima continua: item de outro workflow lido e consumido após a limpeza
    lid = cenario["legit"]["id"]
    cons = _job(tmp_path, remote, "analyze", 902, "analyze", cenario["srv"], workflow="er-analyze",
                extra={"AIMEM_CLAIM_ID": lid})
    assert [i for i in fila(cons) if i["id"] == lid][0]["state"] == "pending"
    rr = cons.session(label="consome")
    assert rr.returncode == 0, rr.stderr[-400:]
    assert cons.received() == cenario["legit"]["summary"]
    assert cons.commit("consome").returncode == 0
    item = json.loads(git(remote, "show", f"main:{cenario['legit_path']}"))
    assert item["state"] == "consumed" and item["consumer"]["consumer_id"].endswith(":902")


def test_trailers_de_proveniencia_nos_commits(cenario):
    msgs = git(cenario["remote"], "log", "--format=%B%x01", "main").split("\x01")
    run = [m for m in msgs if f"Aimem-Run-Id: {R}\n" in m]
    assert run and all(f"Aimem-Workflow: {WF}" in m and "Aimem-Run-Attempt: 1" in m for m in run)
    assert {re.search(r"Aimem-Job: (\S+)", m).group(1) for m in run} == {"job-a", "job-b"}
    human = [m for m in msgs if "estado prévio (humano)" in m]
    assert human and "Aimem-" not in human[0]


def test_sem_github_run_id_sem_trailers(tmp_path, monkeypatch):
    import importlib, sys
    sys.path.insert(0, str(CODE))
    gs = importlib.import_module("aimem.gitsync")
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    assert gs._run_trailers() == ""
    monkeypatch.setenv("GITHUB_RUN_ID", "7"); monkeypatch.setenv("GITHUB_WORKFLOW", "w\nInjetado: x")
    monkeypatch.setenv("GITHUB_JOB", "job-a")
    t = gs._run_trailers()
    assert "Aimem-Run-Id: 7" in t and "\nInjetado" not in t and "Aimem-Workflow: w Injetado: x" in t


# ------------------------------------------------------------------ negativos
def _neg(cenario, tmp_path, mutate_manifest=None, mutate_repo=None, recompute=True, extra=(), esperado="."):
    remote, c = _fresh(cenario, tmp_path)
    if mutate_repo:
        mutate_repo(remote, tmp_path)
        git(c.dir, "pull", "-q", "--ff-only", "origin", "main")
    raw, msha = cenario["manifest"].read_bytes(), cenario["sha"]
    if mutate_manifest:
        obj = json.loads(raw)
        mutate_manifest(obj, c)
        raw = _canon(obj)
        if recompute:
            msha = _sha(raw)
    mp = tmp_path / "m.json"; mp.write_bytes(raw)
    before_local, before_remote = tree_local(c.dir), tree_remote(remote)
    r = _limpa(c, mp, msha, cenario["run_base"], *extra)
    _assert_nada_apagado(remote, c, r, before_local, before_remote, esperado)


def _entry_for(cen, path, c):
    e = dict(_manifest(cen)["entries"][0])
    p = c.dir / path
    blob = p.read_bytes() if p.is_file() and not p.is_symlink() else b""
    e.update(path=path, sha256=_sha(blob), sha256_criacao=_sha(blob))
    adds = git(c.dir, "log", "--diff-filter=A", "--format=%H", "origin/main", "--", path).split()
    if adds:
        e["created_commit"] = adds[0]
    return e


def _atacante(remote, tmp):
    w = tmp / "atacante"; git(tmp, "clone", "-q", str(remote), str(w))
    git(w, "config", "user.name", "x"); git(w, "config", "user.email", "x@x")
    return w


def test_neg_conteudo_modificado(cenario, tmp_path):
    def mut(remote, tmp):
        w = _atacante(remote, tmp)
        p = w / FILA / f"{HID}.json"; p.write_text(p.read_text().replace("prova", "PROVA-ALTERADA", 1))
        git(w, "commit", "-qam", "altera"); git(w, "push", "-q", "origin", "HEAD:main")
    _neg(cenario, tmp_path, mutate_repo=mut, esperado="hash divergente")


@pytest.mark.parametrize("kind", ["adiciona", "remove", "altera"])
def test_neg_manifesto_adulterado_hash_nao_confere(cenario, tmp_path, kind):
    def mut(obj, c):
        if kind == "adiciona":
            obj["entries"].append(_entry_for(cenario, cenario["legit_path"], c))
        elif kind == "remove":
            obj["entries"].pop()
        else:
            obj["entries"][0]["sha256"] = "0" * 64
    _neg(cenario, tmp_path, mutate_manifest=mut, recompute=False, esperado="manifesto adulterado")


def test_neg_manifesto_adulterado_com_hash_recalculado(cenario, tmp_path):
    """Mesmo com o hash recalculado (quem controla o canal), a proveniência barra o item legítimo."""
    _neg(cenario, tmp_path,
         mutate_manifest=lambda o, c: o["entries"].append(_entry_for(cenario, cenario["legit_path"], c)),
         esperado="commit de criação")


@pytest.mark.parametrize("path", [LOOKALIKE, PROVA_B_OUTRO_DIA, AMBIG[0], AMBIG[1], RECUP])
def test_neg_nome_parecido_preexistente(cenario, tmp_path, path):
    _neg(cenario, tmp_path, mutate_manifest=lambda o, c: o["entries"].append(_entry_for(cenario, path, c)),
         esperado="commit de criação")


def test_neg_criado_por_outro_run(cenario, tmp_path):
    _neg(cenario, tmp_path,
         mutate_manifest=lambda o, c: o["entries"].append(_entry_for(cenario, OTHER_RUN_FILE, c)),
         esperado="não pertence a este run")


@pytest.mark.parametrize("path,esperado", [
    ("docs/memory/../README.md", "traversal"),
    ("/etc/passwd", "absoluto"),
    ("docs/memory/paginas/regras.md", "fora do escopo"),
    (RECUP_RAW, "fora do escopo"),
    ("README.md", "fora do escopo"),
    (f"{FILA}/./x.json", "traversal"),
    (f"{FILA}/.gitkeep", "nome fora do escopo"),
    (SYMLINK, "symlink"),
])
def test_neg_fora_do_escopo_traversal_symlink(cenario, tmp_path, path, esperado):
    def mut(o, c):
        e = dict(o["entries"][0]); e["path"] = path; o["entries"].append(e)
    _neg(cenario, tmp_path, mutate_manifest=mut, esperado=esperado)


def test_neg_duplicidade(cenario, tmp_path):
    _neg(cenario, tmp_path, mutate_manifest=lambda o, c: o["entries"].append(dict(o["entries"][0])),
         esperado="duplicidade")


def test_neg_arquivo_ausente(cenario, tmp_path):
    def mut(o, c):
        e = dict(o["entries"][0]); e["path"] = f"{FILA}/nao-existe.json"; o["entries"].append(e)
    _neg(cenario, tmp_path, mutate_manifest=mut, esperado="ausente")


def test_neg_arquivo_do_manifesto_apagado_antes(cenario, tmp_path):
    def mut(remote, tmp):
        w = _atacante(remote, tmp)
        git(w, "rm", "-q", f"{FILA}/{HID}.json"); git(w, "commit", "-qm", "rm"); git(w, "push", "-q", "origin", "HEAD:main")
    _neg(cenario, tmp_path, mutate_repo=mut, esperado="ausente")


@pytest.mark.parametrize("extra", [("--attempt", "2"), ("--run-id", str(OTHER_RUN))])
def test_neg_run_attempt_divergente(cenario, tmp_path, extra):
    _neg(cenario, tmp_path, extra=extra, esperado="run/attempt divergente")


def test_neg_run_base_divergente(cenario, tmp_path):
    remote, c = _fresh(cenario, tmp_path)
    before_local, before_remote = tree_local(c.dir), tree_remote(remote)
    r = _limpa(c, cenario["manifest"], cenario["sha"], git(c.dir, "rev-parse", "origin/main~3"))
    _assert_nada_apagado(remote, c, r, before_local, before_remote, "run_base divergente")


def test_verifica_falha_se_algo_fora_do_manifesto_muda(cenario, tmp_path):
    remote, c = _fresh(cenario, tmp_path)
    antes = tmp_path / "antes.json"
    assert script(c, "snapshot", "--ref", "origin/main", "--out", str(antes)).returncode == 0
    assert _limpa(c, cenario["manifest"], cenario["sha"], cenario["run_base"]).returncode == 0
    _human_commit(c.dir, {AMBIG[0]: "alterado depois\n"}, "mexe em ambíguo")
    git(c.dir, "fetch", "-q", "origin")
    v = script(c, "verifica", "--antes", str(antes), "--manifest", str(cenario["manifest"]),
               "--manifest-sha256", cenario["sha"], "--ref", "origin/main")
    assert v.returncode != 0 and AMBIG[0] in v.stderr


# ------------------------------------------------------------------ workflow / filtro de paths
WFPATH = CODE / ".github/workflows/er-memory-persist.yml"
PATHS_ESPERADOS = [
    ".github/workflows/er-memory-persist.yml",
    "aimem/**",
    "scripts/aimem_commit.sh",
    "scripts/aimem_limpa_prova.py",
    "pyproject.toml",
    ".github/actions/setup-aimemory/**",
]


def _on_push_paths(text: str) -> list[str]:
    on = re.search(r"^on:\n(.*?)(?=^\S)", text, re.M | re.S).group(1)
    push = re.search(r"^  push:\n(.*?)(?=^  \S|\Z)", on, re.M | re.S).group(1)
    block = re.search(r"^    paths:\n((?:      .*\n)+)", push, re.M).group(1)
    return [m.group(1) for m in re.finditer(r'^      - "([^"]+)"\s*$', block, re.M)]


def test_filtro_paths_conjunto_exato():
    assert _on_push_paths(WFPATH.read_text()) == PATHS_ESPERADOS


def test_workflow_executa_so_coisas_cobertas_pelo_filtro():
    text = WFPATH.read_text()
    assert set(re.findall(r"scripts/[\w.-]+", text)) <= {"scripts/aimem_commit.sh", "scripts/aimem_limpa_prova.py"}
    assert set(re.findall(r"uses: \./(\.github/actions/[\w-]+)", text)) <= {".github/actions/setup-aimemory"}
    code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    assert "pytest" not in code and "tests/" not in code  # por isso tests/p0a/** não está no filtro


def _code(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


def test_workflow_ordem_e_amarracao_do_manifesto():
    text = WFPATH.read_text()
    assert "manifest_sha256: ${{ steps.manifesto.outputs.manifest_sha256 }}" in text
    jc = text[text.index("\n  job-c:\n"):]
    i_rec = jc.index("- name: Recover handoff perdido")
    i_dl = jc.index("actions/download-artifact@v4")
    i_limpa = jc.index("- name: Limpeza da prova em DRY-RUN")
    assert i_rec < i_dl < i_limpa
    bloco = jc[i_limpa:]
    for s in ("cmp ", "limpa --manifest", "--manifest-sha256", "--run-base", "--relatorio", "verifica --esperado intacto"):
        assert s in bloco, s
    assert bloco.index("limpa --manifest") < bloco.index("verifica --esperado intacto")
    assert "prova-limpeza-dry-run-${{ github.run_id }}-${{ github.run_attempt }}" in bloco


def test_workflow_nunca_apaga_em_nenhum_evento():
    """D: nenhum passo do workflow (push ou workflow_dispatch) passa --confirmar → o script nunca faz unlink;
    depois do download do manifesto, o job-c não commita nem empurra nada."""
    text = WFPATH.read_text(); code = _code(text)
    assert "--confirmar" not in code and "confirmar" not in code
    jc = code[code.index("\n  job-c:\n"):]
    pos = jc[jc.index("actions/download-artifact@v4"):]
    for proibido in ("aimem_commit.sh", "git push", "git commit", "git rm", "rm -", "unlink", "AIMEM_SYNC_REF"):
        assert proibido not in pos, proibido
    # o passo de limpeza não depende de evento (nenhum if: que libere exclusão em algum evento)
    i = pos.index("- name: Limpeza da prova em DRY-RUN"); passo = pos[i:pos.index("- name:", i + 5)]
    assert "if:" not in passo


def test_script_sem_regra_por_nome():
    src = pathlib.Path(SCRIPT).read_text()
    for proibido in ("prova-b", "persist-prova", '"recovery"', '"migration"', "sess_re"):
        assert proibido not in src, proibido


# ------------------------------------------------------------------ D: dry-run por padrão + confirmação explícita
def test_limpa_sem_confirmar_e_dry_run_sem_unlink(cenario, tmp_path):
    remote, c = _fresh(cenario, tmp_path)
    bl, br = tree_local(c.dir), tree_remote(remote)
    rel = tmp_path / "rel.json"
    r = _limpa(c, cenario["manifest"], cenario["sha"], cenario["run_base"], "--relatorio", str(rel), confirmar=False)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.splitlines()[-1])
    assert out["dry_run"] is True and out["removidos"] == []
    assert set(out["seriam_removidos"]) == {e["path"] for e in _manifest(cenario)["entries"]}
    assert json.loads(rel.read_text()) == out
    assert tree_local(c.dir) == bl and tree_remote(remote) == br          # zero exclusões
    antes = tmp_path / "antes.json"
    assert script(c, "snapshot", "--ref", "origin/main", "--out", str(antes)).returncode == 0
    v = script(c, "verifica", "--esperado", "intacto", "--antes", str(antes), "--manifest", str(cenario["manifest"]),
               "--manifest-sha256", cenario["sha"], "--ref", "origin/main")
    assert v.returncode == 0, v.stderr


@pytest.mark.parametrize("conf", ["0" * 64, "abc", ""])
def test_limpa_confirmacao_errada_aborta_sem_unlink(cenario, tmp_path, conf):
    remote, c = _fresh(cenario, tmp_path)
    bl, br = tree_local(c.dir), tree_remote(remote)
    r = script(c, "limpa", "--manifest", str(cenario["manifest"]), "--manifest-sha256", cenario["sha"],
               "--run-base", cenario["run_base"], "--ref", "origin/main", "--confirmar", conf)
    _assert_nada_apagado(remote, c, r, bl, br, "confirmar não confere")


def test_limpa_dry_run_explicito_vence_confirmar(cenario, tmp_path):
    remote, c = _fresh(cenario, tmp_path)
    bl, br = tree_local(c.dir), tree_remote(remote)
    r = _limpa(c, cenario["manifest"], cenario["sha"], cenario["run_base"], "--dry-run")
    assert r.returncode == 0 and json.loads(r.stdout.splitlines()[-1])["removidos"] == []
    assert tree_local(c.dir) == bl and tree_remote(remote) == br


def test_verifica_intacto_falha_apos_exclusao_real(cenario, tmp_path):
    remote, c = _fresh(cenario, tmp_path)
    antes = tmp_path / "antes.json"
    assert script(c, "snapshot", "--ref", "origin/main", "--out", str(antes)).returncode == 0
    assert _limpa(c, cenario["manifest"], cenario["sha"], cenario["run_base"]).returncode == 0
    git(c.dir, "fetch", "-q", "origin")
    v = script(c, "verifica", "--esperado", "intacto", "--antes", str(antes), "--manifest", str(cenario["manifest"]),
               "--manifest-sha256", cenario["sha"], "--ref", "origin/main")
    assert v.returncode == 1


def test_charset_igual_em_aimem_e_na_limpeza():
    import importlib.util, sys
    sys.path.insert(0, str(CODE))
    nomes = importlib.import_module("aimem.nomes")
    spec = importlib.util.spec_from_file_location("lp_charset", SCRIPT); lp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lp)
    assert lp.SAFE_NAME.pattern == nomes.SAFE_NAME_RE

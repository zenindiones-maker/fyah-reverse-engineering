"""D2 — todo nome de arquivo de memória é validado ANTES da escrita; criação × sincronização × limpeza coerentes;
o YAML não escreve arquivo de memória inline (só via aimem, que valida)."""
from __future__ import annotations

import importlib.util, json, os, pathlib, random, re, sys

import pytest

from tests.p0a.helpers import CODE, PY, Job, git, make_remote

sys.path.insert(0, str(CODE))
from aimem import effects, ledger, nomes  # noqa: E402

SCRIPT = str(CODE / "scripts" / "aimem_limpa_prova.py")
_spec = importlib.util.spec_from_file_location("lp_d2", SCRIPT); lp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lp)
WORKFLOWS = sorted((CODE / ".github" / "workflows").glob("*.yml"))


def _listagem(d: pathlib.Path) -> list[str]:
    """Tudo sob docs/memory (inclui dirs, dotfiles e temporários) — prova de que nada foi criado."""
    return sorted(str(p.relative_to(d)) for p in (d / "docs" / "memory").rglob("*"))


# ------------------------------------------------------------------ validação antes da escrita
@pytest.mark.parametrize("run_id,attempt", [("1 2", "1"), ("../x", "1"), ("a\nb", "1"), ("ç", "1"), ("1;rm", "1"),
                                            ("7", "1\n"), ("7", "1/2"), ("", "1"), ("7", "x" * 300)])
def test_prova_item_nome_invalido_nao_cria_nada(tmp_path, run_id, attempt):
    remote = make_remote(tmp_path)
    j = Job(tmp_path, remote, "a", run_id=1, workflow="er-memory-persist")
    j.env["GITHUB_RUN_ID"] = run_id; j.env["GITHUB_RUN_ATTEMPT"] = attempt
    antes = _listagem(j.dir)
    gho = tmp_path / "gho"
    r = j.run(PY, "-m", "aimem", "prova-item", "--summary", "s", "--github-output", str(gho))
    if run_id == "":                                   # ledger.me() cai em "local" → nome válido; aqui não é erro
        assert r.returncode == 0, r.stderr
        return
    assert r.returncode == 2 and "nada foi criado" in r.stderr, (r.returncode, r.stderr[-300:])
    assert _listagem(j.dir) == antes                   # nenhum arquivo/dir novo
    assert git(j.dir, "status", "--porcelain", "--untracked-files=all") == ""
    assert not gho.exists()                            # nenhum output de id inválido


def test_prova_item_fora_do_workflow_de_prova_recusa_sem_criar(tmp_path):
    remote = make_remote(tmp_path)
    j = Job(tmp_path, remote, "a", run_id=5, workflow="er-toolcheck")
    antes = _listagem(j.dir)
    r = j.run(PY, "-m", "aimem", "prova-item", "--summary", "s")
    assert r.returncode == 2 and "workflow de prova" in r.stderr
    assert _listagem(j.dir) == antes


def test_prova_item_nunca_sobrescreve(tmp_path):
    remote = make_remote(tmp_path)
    j = Job(tmp_path, remote, "a", run_id=5, workflow="er-memory-persist")
    assert j.run(PY, "-m", "aimem", "prova-item", "--summary", "s1").returncode == 0
    p = j.dir / "docs/memory/handoffs/fila/persist-prova-a-5-1.json"; b1 = p.read_bytes()
    r = j.run(PY, "-m", "aimem", "prova-item", "--summary", "s2")
    assert r.returncode == 2 and "já existe" in r.stderr and p.read_bytes() == b1


def test_ledger_save_invalido_nao_cria_nem_o_diretorio(tmp_path):
    mem = tmp_path / "mem"
    for bad in ("x y", "../x", "-x", ".x", "a\n", "é"):
        with pytest.raises(nomes.NomeInvalido):
            ledger.save(mem, {"id": bad})
    assert not mem.exists()


def test_efeito_invalido_nao_cria_nem_o_diretorio(tmp_path):
    mem = tmp_path / "mem"
    h = {"id": "!x", "consumer": {"claim_token": "t", "attempt_id": "1.1", "consumer_id": "w:1"}}
    with pytest.raises(nomes.NomeInvalido):
        effects.apply(mem, h, {})
    assert not mem.exists()


# ------------------------------------------------------------------ criação × sincronização × limpeza
_ALFA = "aZ09._:-" + " \t\n\"'\\/[]*?!@#$%&()é\u0301ç~`^{}|<>;,=+"


def _corpus() -> list[str]:
    rnd = random.Random(20261019)
    fixos = ["ok.md", "ok.json", "x.md\n", "x.json\n", "\nx.md", "a" * 197 + ".md", "a" * 198 + ".md",
             "a" * 300 + ".json", ".gitkeep", "-x.md", ":x.md", "_x.md", "A_b.c-1.json", "a:b.json", "x.MD", "x.md.bak",
             "persist-prova-a-1-1.json", "persist-prova-a-1-1:0e5ce265fd384f3b8b21c5d60f905fe1.json", "café.md",
             "cafe\u0301.md", "x .md", " x.md", "x\x00.md", "x\r.md", "x\u2028.md", "ｘ.md", "x.md ", "x.json\t"]
    gerados = ["".join(rnd.choice(_ALFA) for _ in range(rnd.randint(1, 12))) + rnd.choice([".md", ".json", ".txt", ""])
               for _ in range(400)]
    validos_like = [rnd.choice("aZ9") + "".join(rnd.choice("aZ09._:-") for _ in range(rnd.randint(0, 20)))
                    + rnd.choice([".md", ".json"]) for _ in range(150)]
    return fixos + gerados + validos_like


def _cria_ok(n):
    try:
        nomes.valida_nome(n); return True
    except nomes.NomeInvalido:
        return False


def test_criacao_e_limpeza_aceitam_exatamente_o_mesmo_conjunto():
    """Quebra se uma camada aceitar o que a outra rejeita (em qualquer direção)."""
    div = [n for n in _corpus() if _cria_ok(n) != (lp.check_path(f"docs/memory/sessoes/{n}") is None)]
    assert div == [], [repr(x) for x in div[:10]]
    assert lp.SAFE_NAME_MAX == nomes.MAX_LEN and lp.SAFE_NAME.pattern == nomes.SAFE_NAME_RE


def test_tudo_que_a_criacao_aceita_o_gitsync_sincroniza(tmp_path):
    aceitos = sorted({n for n in _corpus() if _cria_ok(n)})
    assert len(aceitos) > 100
    remote = make_remote(tmp_path)
    j = Job(tmp_path, remote, "s", run_id=9, workflow="er-toolcheck")
    for n in aceitos:
        (j.dir / "docs/memory/sessoes" / n).write_text(f"conteúdo {n}\n")
    r = j.run(PY, "-m", "aimem", "sync", "--msg", "corpus")
    assert r.returncode == 0, r.stderr[-400:]
    out = git(remote, "ls-tree", "-r", "-z", "--name-only", "main", "--", "docs/memory/sessoes").split("\0")
    assert {p.rsplit("/", 1)[1] for p in out if p} >= set(aceitos)
    assert git(j.dir, "status", "--porcelain") == ""


def test_trailing_newline_rejeitado_nas_duas_camadas():
    """Achado D2: `$` em Python casa antes de \\n final; D original aceitava 'x.md\\n' na criação."""
    for n in ("x.md\n", "x.json\n"):
        assert not _cria_ok(n)
        assert lp.check_path(f"docs/memory/sessoes/{n}") is not None


# ------------------------------------------------------------------ YAML: nenhuma escrita inline de memória
_ESCRITA_PY = re.compile(r"write_text|write_bytes|\bopen\(|mkdir|unlink|os\.remove|os\.rename|os\.replace|shutil\.|"
                         r"\.rename\(|\.replace\(|\.touch\(|rmtree")
_ESCRITA_SH = re.compile(r"(>>?|\btee\b|\bcp\b|\bmv\b|\btouch\b|\bmkdir\b|\brm\b|\bln\b|\bsed -i|\binstall\b)")


def _heredocs(text: str):
    for m in re.finditer(r"python3? - <<'?(\w+)'?\n(.*?)\n\s*\1\n", text, re.S):
        yield m.group(2)


def _shell_sem_heredoc(text: str) -> str:
    return re.sub(r"python3? - <<'?(\w+)'?\n.*?\n\s*\1\n", "\n", text, flags=re.S)


@pytest.mark.parametrize("wf", WORKFLOWS, ids=lambda p: p.name)
def test_yaml_nao_escreve_memoria_inline(wf):
    text = wf.read_text()
    for body in _heredocs(text):
        if "docs/memory" in body or "fila" in body or "handoffs" in body:
            achados = _ESCRITA_PY.findall(body)
            assert not achados, (wf.name, achados, body[:200])
    for n, line in enumerate(_shell_sem_heredoc(text).splitlines(), 1):
        s = re.sub(r"\d?>>?\s*/dev/null", "", line.split("#", 1)[0])   # descarte em /dev/null não é escrita
        if "docs/memory" not in s:
            continue
        if re.search(r"\bgit (checkout|show|ls-tree|log|diff|status|rev-parse)\b", s):
            continue                                  # leitura/restauração a partir do git (não cria nomes)
        assert not _ESCRITA_SH.search(s), (wf.name, n, s.strip())


def test_job_a_usa_o_validador():
    text = (CODE / ".github/workflows/er-memory-persist.yml").read_text()
    ja = text[text.index("\n  job-a:\n"):text.index("\n  job-b:\n")]
    assert "python -m aimem prova-item" in ja
    assert "write_text" not in ja and "persist-prova-a-" not in ja   # id e escrita só no aimem (validado)


# ------------------------------------------------------------------ D2 (revisão integral dos pontos de criação)
def _mds(d: pathlib.Path) -> list[str]:
    m = d / "docs" / "memory"
    return sorted(str(p.relative_to(m)) for p in [*m.glob("sessoes/**/*"), *m.glob("handoffs/*.md")])


def test_sessao_com_run_id_hostil_nao_cria_md_nem_item(tmp_path):
    """_persist monta e valida o id do item da fila ANTES de escrever sessoes/*.md e handoffs/*.md."""
    from tests.p0a.fakeserver import FakeAIMemory
    remote = make_remote(tmp_path)
    srv = FakeAIMemory(tmp_path / "srv")
    try:
        j = Job(tmp_path, remote, "h", run_id=1, server=srv, workflow="er-toolcheck")
        j.env["GITHUB_RUN_ID"] = "1 2"
        antes = _mds(j.dir)
        r = j.session(label="x")
        assert r.returncode != 0 and "NomeInvalido" in r.stderr, r.stderr[-400:]
        assert _mds(j.dir) == antes                            # nenhum sessoes/*.md nem handoffs/*.md escrito
        assert not [p for p in _listagem(j.dir) if "1 2" in p]  # nenhum item/diretório com o id hostil
    finally:
        srv.close()


@pytest.mark.parametrize("op", ["migrate", "recover"])
def test_migrate_recover_nome_invalido_nao_cria_raw_nem_diretorio(tmp_path, monkeypatch, op):
    remote = make_remote(tmp_path)
    j = Job(tmp_path, remote, "m", run_id=1, workflow="er-toolcheck")
    mem = j.dir / "docs" / "memory"
    import shutil
    shutil.rmtree(mem / "handoffs" / "raw")                    # o diretório também não pode ser criado
    antes = _listagem(j.dir)
    real = ledger._item_from_aberto
    monkeypatch.setattr(ledger, "_item_from_aberto", lambda *a, **k: dict(real(*a, **k), id="../fora"))
    with pytest.raises(nomes.NomeInvalido):
        if op == "migrate":
            ledger.migrate_aberto(mem)
        else:
            ledger.recover_lost(mem, "HEAD", "HEAD", "docs/memory/handoffs/aberto.json", "t", repo=j.dir)
    assert _listagem(j.dir) == antes and not (mem / "handoffs" / "raw").exists()


@pytest.mark.parametrize("iid", ["../efeitos/x", "a b", "-x", "x\n", "../../README"])
def test_claim_id_invalido_e_lost_sem_ler_nem_escrever(tmp_path, iid):
    from tests.p0a.fakeserver import FakeAIMemory
    remote = make_remote(tmp_path)
    t0 = git(remote, "ls-tree", "-r", "main")
    srv = FakeAIMemory(tmp_path / "srv")
    try:
        j = Job(tmp_path, remote, "c", run_id=3, server=srv, workflow="er-toolcheck", extra_env={"AIMEM_CLAIM_ID": iid})
        r = j.session(label="x")
        assert r.returncode == 0 and '"claim_status": "lost"' in r.stdout and "inválido" in r.stdout, r.stdout[-400:]
        assert not list((j.dir / "docs/memory/handoffs/efeitos").glob("*.json"))  # nenhum efeito para id inválido
        fora = git(j.dir, "status", "--porcelain", "--untracked-files=all", "--", ".", ":!out", ":!docs/memory")
        assert fora == "" and not (j.dir / "README").exists()
        assert all(json.loads(p.read_text()).get("state") != "claimed"
                   for p in (j.dir / "docs/memory/handoffs/fila").glob("*.json"))
    finally:
        srv.close()
    t1 = git(remote, "ls-tree", "-r", "main")
    assert [l for l in t1.splitlines() if "docs/memory" not in l] == [l for l in t0.splitlines() if "docs/memory" not in l]


def test_id_forjado_no_conteudo_nunca_e_oferecido(tmp_path):
    """Arquivo válido da fila cujo `id` interno aponta para fora: claim_one não o oferece (nada lido/escrito fora)."""
    from tests.p0a.fakeserver import FakeAIMemory
    import shutil
    src = tmp_path / "mem"; shutil.copytree(make_remote.__globals__["synthetic_memory"](tmp_path / "base"), src)
    (src / "handoffs" / "aberto.json").unlink()
    it = ledger.new_item("legit?", [], [], [], {"workflow": "er-toolcheck", "run_id": "1", "run_attempt": "1", "sha": None,
                                                 "session": "s", "agent": "a", "created_utc": "2026-10-19T00:00:00Z"})
    it["id"] = "../../README"
    (src / "handoffs" / "fila" / "forjado.json").write_text(ledger.dumps(it))
    remote = make_remote(tmp_path / "r", memory_from=src)
    t0 = git(remote, "ls-tree", "-r", "main")
    srv = FakeAIMemory(tmp_path / "srv")
    try:
        j = Job(tmp_path, remote, "c", run_id=4, server=srv, workflow="er-toolcheck")
        r = j.session(label="x")
        assert r.returncode == 0
        assert json.loads((j.dir / "out/aimem/session-ag-c.json").read_text())["handoff_claimed_id"] is None
    finally:
        srv.close()
    t1 = dict(l.split("\t", 1)[::-1] for l in git(remote, "ls-tree", "-r", "main").splitlines())
    t0d = dict(l.split("\t", 1)[::-1] for l in t0.splitlines())
    assert t1["README.md"] == t0d["README.md"] and t1["docs/memory/handoffs/fila/forjado.json"] == t0d["docs/memory/handoffs/fila/forjado.json"]

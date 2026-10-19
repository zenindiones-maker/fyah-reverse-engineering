"""D — nomes de memória: nada pode ser criado-e-perdido.

(a) gitsync sincroniza QUALQUER nome válido em docs/memory (porcelain -z + pathspec literal);
(b) o aimem só cria nomes no charset de aimem/nomes.py e falha alto (antes de criar) fora dele.
"""
from __future__ import annotations

import json, pathlib, re, subprocess, sys

import pytest

from tests.p0a.helpers import CODE, PY, Job, git, make_remote

sys.path.insert(0, str(CODE))
from aimem import nomes, ledger, effects  # noqa: E402

SESS = "docs/memory/sessoes"
PROBLEMATICOS = ["com espaço.md", "café.md", "cafe\u0301-nfd.md", "aspas\".md", "back\\slash.md", "nl\nx.md",
                 "tab\tx.md", " lead.md", "trail.md ", "a -> b.md", "[ab].md", "-traco.md", ":magic.md"]


def _tree(remote):
    raw = subprocess.run(["git", "ls-tree", "-r", "-z", "--name-only", "main", "--", "docs/memory"], cwd=remote,
                         capture_output=True, check=True).stdout.decode()
    return {x for x in raw.split("\0") if x}


# ------------------------------------------------------------------ (a) gitsync sincroniza qualquer nome
def test_gitsync_sincroniza_nomes_problematicos(tmp_path):
    remote = make_remote(tmp_path)
    j = Job(tmp_path, remote, "q", run_id=1, workflow="er-aimemory", extra_env={"GITHUB_JOB": "j"})
    for n in PROBLEMATICOS:
        (j.dir / SESS / n).write_text(f"conteúdo {n!r}\n")
    r = j.commit("nomes"); assert r.returncode == 0, r.stderr
    t = _tree(remote)
    falt = [n for n in PROBLEMATICOS if f"{SESS}/{n}" not in t]
    assert falt == [], f"memória criada e NÃO sincronizada: {falt}"
    # conteúdo byte a byte
    for n in PROBLEMATICOS:
        blob = subprocess.run(["git", "show", f"main:{SESS}/{n}"], cwd=remote, capture_output=True, check=True).stdout
        assert blob == f"conteúdo {n!r}\n".encode()


def test_gitsync_pathspec_literal_nao_arrasta_arquivo_vizinho(tmp_path):
    """Nome com metacaractere de glob ('[p]aginas.md') é estagiado literalmente; paginas/ (curadoria humana)
    continua fora mesmo que o glob casasse 'paginas'."""
    remote = make_remote(tmp_path)
    j = Job(tmp_path, remote, "g", run_id=2, workflow="er-aimemory", extra_env={"GITHUB_JOB": "j"})
    (j.dir / "docs/memory/paginas/x.md").write_text("curadoria humana\n")
    (j.dir / "docs/memory/sessoes/[p]aginas.md").write_text("glob\n")
    r = j.commit("glob"); assert r.returncode == 0, r.stderr
    t = _tree(remote)
    assert "docs/memory/sessoes/[p]aginas.md" in t
    assert "docs/memory/paginas/x.md" not in t           # paginas/ nunca é estagiado


def test_gitsync_remocao_com_nome_problematico_e_publicada(tmp_path):
    remote = make_remote(tmp_path)
    j = Job(tmp_path, remote, "r", run_id=3, workflow="er-aimemory", extra_env={"GITHUB_JOB": "j"})
    (j.dir / SESS / "com espaço.md").write_text("x\n")
    assert j.commit("cria").returncode == 0
    (j.dir / SESS / "com espaço.md").unlink()
    r = j.commit("remove"); assert r.returncode == 0, r.stderr
    assert f"{SESS}/com espaço.md" not in _tree(remote)


# ------------------------------------------------------------------ (b) criação com falha alta
@pytest.mark.parametrize("bad", ["com espaço", "café", "a/b", "../x", ".oculto", "-x", ":x", "nl\nx", "x" * 300])
def test_ledger_save_falha_alto_antes_de_criar(tmp_path, bad):
    item = {"id": bad}
    with pytest.raises(nomes.NomeInvalido):
        ledger.save(tmp_path, item)
    assert not (tmp_path / "handoffs" / "fila").exists() or not any((tmp_path / "handoffs" / "fila").iterdir())


def test_ids_gerados_pelo_ledger_estao_no_charset(monkeypatch):
    for rid, att in (("39190430768", "1"), ("local", "1")):
        monkeypatch.setenv("GITHUB_RUN_ID", rid); monkeypatch.setenv("GITHUB_RUN_ATTEMPT", att)
        o = ledger.origin_from_env("s", "a")
        nomes.valida_nome(ledger.new_item("x", [], [], [], o)["id"] + ".json")


def test_id_com_env_hostil_falha_alto_no_save(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "1 2"); monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    it = ledger.new_item("x", [], [], [], ledger.origin_from_env("s", "a"))
    with pytest.raises(nomes.NomeInvalido):
        ledger.save(tmp_path, it)


def test_efeito_nome_sanitizado_e_validado(tmp_path):
    k = effects.effect_key("20261019T000000Z-1-1-abcdef", "tok/../en ç", "1.1")
    nomes.valida_nome(k + ".json")
    assert effects.path_for(tmp_path, k).name == k + ".json"
    with pytest.raises(nomes.NomeInvalido):
        effects.path_for(tmp_path, "com espaço")


def test_migracao_e_recover_geram_nomes_no_charset(tmp_path):
    from tests.p0a.helpers import LEGACY_ABERTO
    mem = tmp_path / "mem"; (mem / "handoffs").mkdir(parents=True)
    (mem / "handoffs" / "aberto.json").write_text(LEGACY_ABERTO)
    it = ledger.migrate_aberto(mem, by="t")
    nomes.valida_nome(it["id"] + ".json")
    nomes.valida_nome(pathlib.Path(it["migration"]["raw_path"]).name)


@pytest.mark.parametrize("label", ["prova-B", "Café com Espaço", "a/b\\c", "nl\nx", "!!!", "x" * 300])
def test_sessao_com_label_hostil_gera_nome_seguro_e_sincroniza(tmp_path, label):
    remote = make_remote(tmp_path)
    j = Job(tmp_path, remote, "s", run_id=5, workflow="er-aimemory", extra_env={"GITHUB_JOB": "j"})
    r = j.run(PY, "-m", "aimem", "session", "--agent", "ag", "--label", label, "--", "true")
    assert r.returncode == 0, r.stderr[-400:]
    assert j.commit("sessao").returncode == 0
    t = _tree(remote)
    novos = [p for p in t if p.startswith(("docs/memory/sessoes/2", "docs/memory/handoffs/2"))]
    assert len(novos) == 2, novos
    for p in novos:
        nomes.valida_nome(pathlib.PurePosixPath(p).name)


def test_charset_unico():
    assert nomes.SAFE_NAME.pattern == nomes.SAFE_NAME_RE
    src = (CODE / "scripts" / "aimem_limpa_prova.py").read_text()
    assert f'SAFE_NAME = re.compile(r"{nomes.SAFE_NAME_RE}")' in src

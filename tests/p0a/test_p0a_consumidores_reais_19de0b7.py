"""D2 — regressão: consumidores reais em SEQUÊNCIA sobre o docs/memory INTEIRO do remoto real.

Estado = `git archive 19de0b7 docs/memory` do objeto git (p0a publicado), conferido byte a byte (árvore `docs/memory`
do remoto-fixture == árvore do commit). Segundo estado: o mesmo docs/memory SEM as 3 provas legadas (04d891,
persist-prova-a-39190430768-1 e o efeito dele), derivado de 19de0b7 removendo-as explicitamente e conferido pela árvore
85abd05f… — cobre a fila com e sem as provas legadas usando só o objeto publicado 19de0b7. Contém o item de prova
legado 04d891
("[prova-B]…", pending, sem `kind`), as 2 `.md` prova-b, o recuperado e49f…, a migração 0e5a7…, persist-prova-a
(consumed) + efeito, raw/ e aberto.json. Consumidores com claim normal (sem AIMEM_CLAIM_ID), servidor por run + seed:
er-toolcheck → er-analyze → er-harness → er-aimemory. Afirma: nenhum recebe item de prova (por marca/origem), nada de
prova é enviado ao servidor na hidratação, prova e demais arquivos preservados byte a byte; só os itens legítimos
consumidos mudam, e só nos campos de claim/consumo.
Precisa dos objetos do histórico (ci.yml usa fetch-depth: 0); ausência = falha, não skip.
"""
from __future__ import annotations

import io, json, pathlib, subprocess, tarfile

import pytest

from tests.p0a.fakeserver import FakeAIMemory
from tests.p0a.helpers import HIST, PY, Job, git, make_remote

FILA = "docs/memory/handoffs/fila"
P04 = f"{FILA}/20261019T023307Z-39190430768-1-04d891.json"
E49F = f"{FILA}/20261018T234221Z-39177110784-1-e49f682ec9e6.json"
M0E5 = f"{FILA}/20261018T234805Z-39177105670-1-0e5a7efa681c.json"
MD_PROVA = ["docs/memory/handoffs/2026-10-19-prova-b-277e23.md", "docs/memory/sessoes/2026-10-19-prova-b-277e23.md"]
ESTADOS = {
    "19de0b7": ("19de0b7df02567eec023334322649500f4c946d9", "0445557ee16250a929a770c494274e35b4d28727", 30),
    # docs/memory de 19de0b7 sem as 3 provas legadas (SEM_3_PROVAS), derivado em teste e conferido pelo SHA da árvore
    "19de0b7-sem-3-provas": ("19de0b7df02567eec023334322649500f4c946d9", "85abd05fd13f1112e09db19c1e5d4dde3e5b8e34", 27),
}
BLOBS_19DE0B7 = {   # git ls-tree 19de0b7 (sha1 completo)
    P04: "f5070c2dd2f1498c89192c9f995817bc607d4238",
    MD_PROVA[0]: "eea5a1e6bca5", MD_PROVA[1]: "20a485152450",
    E49F: "cd4d12d16071", M0E5: "71f45faad3bd",
    f"{FILA}/persist-prova-a-39190430768-1.json": "c23736c0c9e8",
}
CONSUMIDORES = [  # (workflow, agente, label, args extras da sessão)
    ("er-toolcheck", "er-toolcheck", "toolcheck", ["--next", "Consertar o que aparecer como falha em docs/ferramentas/STATUS.md"]),
    ("er-analyze", "er-analyze", "media-inspect", []),
    ("er-harness", "deepseek-harness", "dsh-qwen3-30b-a3b", ["--next", "Revisar out/harness.json e o score de tool-use"]),
    ("er-aimemory", "fyah-tools", "media-inspect", ["--next", "Conferir out/media-inspect.json e decidir o próximo pipeline"]),
]
CAMPOS_CONSUMO = ("attempts", "state", "history", "consumer", "consumed")
SEM_3_PROVAS = [P04, f"{FILA}/persist-prova-a-39190430768-1.json",
                "docs/memory/handoffs/efeitos/persist-prova-a-39190430768-1:0e5ce265fd384f3b8b21c5d60f905fe1.json"]


def _estado(tmp: pathlib.Path, commit: str, remover=()) -> pathlib.Path:
    r = subprocess.run(["git", "archive", "--format=tar", commit, "docs/memory"], cwd=HIST, capture_output=True)
    if r.returncode:
        pytest.fail(f"objeto {commit} ausente em {HIST} (precisa de histórico completo): {r.stderr[-300:]!r}")
    dst = tmp / "estado"
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tf:
        tf.extractall(dst, filter="data")
    for p in remover:
        (dst / p).unlink()                      # FileNotFoundError = estado de origem não é o esperado (falha)
    return dst / "docs" / "memory"


def _ls(remote) -> dict:
    out = {}
    for line in git(remote, "ls-tree", "-r", "-z", "main", "--", "docs/memory").split("\0"):
        if line:
            meta, p = line.split("\t", 1); out[p] = meta.split()[2]
    return out


def _item(remote, blob) -> dict:
    return json.loads(git(remote, "cat-file", "blob", blob))


def _is_prova(it: dict) -> bool:   # independente do código sob teste: marca estrutural ou origem
    return it.get("kind") == "prova" or bool(it.get("prova")) or (it.get("origin") or {}).get("workflow") == "er-memory-persist"


@pytest.mark.parametrize("estado", sorted(ESTADOS))
def test_consumidores_reais_sequenciais_sobre_estado_real(tmp_path, estado):
    commit, tree_esperada, n = ESTADOS[estado]
    derivado = estado.endswith("-sem-3-provas")
    remote = make_remote(tmp_path, memory_from=_estado(tmp_path, commit, SEM_3_PROVAS if derivado else ()))
    assert git(remote, "rev-parse", "main:docs/memory") == tree_esperada
    if not derivado:
        assert tree_esperada == git(HIST, "rev-parse", f"{commit}:docs/memory")
    t0 = _ls(remote)
    assert len(t0) == n
    if estado == "19de0b7":
        for p, b in BLOBS_19DE0B7.items():
            assert t0[p].startswith(b), p
    recebidos = []
    for k, (wf, agent, label, extra) in enumerate(CONSUMIDORES):
        srv = FakeAIMemory(tmp_path / f"srv-{wf}")
        try:
            antes = _ls(remote)
            j = Job(tmp_path, remote, wf, run_id=700001 + k, server=srv, workflow=wf)
            assert j.seed().returncode == 0
            # hidratação: nada de prova vai ao servidor (páginas de sessão de prova nem handoffs/*.md)
            enviados = [a for name, a in srv.calls if name == "memory_write_page"]
            assert enviados and all(not a["path"].startswith("handoffs") for a in enviados)
            assert not any("prova-b-277e23" in a["path"] or "[prova-B]" in a["body"] or "(er-memory-persist)" in a["body"]
                           for a in enviados), [a["path"] for a in enviados]
            r = j.run(PY, "-m", "aimem", "session", "--agent", agent, "--label", label, *extra, "--", "true")
            assert r.returncode == 0, r.stderr[-800:]
            rec = json.loads((j.dir / "out" / "aimem" / f"session-{agent}.json").read_text())
            assert j.commit(wf, label).returncode == 0
            cid = rec.get("handoff_claimed_id")
            assert cid, f"{wf} não recebeu nada (havia memória legítima pendente)"
            it = _item(remote, antes[f"{FILA}/{cid}.json"])
            assert not _is_prova(it), (wf, cid, it.get("summary"))
            assert "[prova" not in (rec.get("handoff_received") or "")
            recebidos.append((wf, cid))
        finally:
            srv.close()
    # os dois legítimos preexistentes chegam primeiro; depois, handoffs legítimos deixados pelos próprios consumidores
    assert [c for _, c in recebidos[:2]] == [pathlib.Path(E49F).stem, pathlib.Path(M0E5).stem]
    assert all("-70000" in c for _, c in recebidos[2:])
    tf_ = _ls(remote)
    assert set(t0) <= set(tf_)                                         # nada removido
    mudaram = {p for p in t0 if tf_[p] != t0[p]}
    assert mudaram == {E49F, M0E5}, mudaram                            # 04d891, .md prova-b, raw/, aberto.json… intactos
    for p in mudaram:
        a, b = _item(remote, t0[p]), _item(remote, tf_[p])
        assert {k for k in set(a) | set(b) if a.get(k) != b.get(k)} <= set(CAMPOS_CONSUMO), p
        assert b["history"][:len(a["history"])] == a["history"] and b["state"] == "consumed"
    if P04 in t0:
        assert tf_[P04] == t0[P04] and _item(remote, tf_[P04])["state"] == "pending"
    # listagem: a prova aparece marcada para quem lista a fila / status
    v = Job(tmp_path, remote, "lista", run_id=709999, workflow="er-toolcheck")
    fila = json.loads(v.run(PY, "-m", "aimem", "fila", "--json").stdout)
    for i in fila:
        assert i["eh_prova"] == _is_prova({k: x for k, x in i.items() if k != "eh_prova"}), i["id"]
    st = json.loads(v.run(PY, "-m", "aimem", "status").stdout)
    assert {i["id"] for i in st["fila"] if i["eh_prova"]} == {i["id"] for i in fila if i["eh_prova"]}
    if estado == "19de0b7":
        assert {i["id"] for i in fila if i["eh_prova"]} == {pathlib.Path(P04).stem, "persist-prova-a-39190430768-1"}

"""Regressão: o remoto de teste não depende do estado vivo de docs/memory do checkout."""
from __future__ import annotations

import inspect

from tests.p0a import helpers
from tests.p0a.helpers import git, make_remote, remote_tree


def test_make_remote_tem_fila_vazia_e_legado_fixo(tmp_path):
    remote = make_remote(tmp_path)
    t = remote_tree(tmp_path / "v", remote)
    mem = t / "docs/memory/handoffs"
    for sub in ("fila", "efeitos", "raw"):
        assert sorted(p.name for p in (mem / sub).iterdir()) == [".gitkeep"], sub
    assert (mem / "aberto.json").read_text() == helpers.LEGACY_ABERTO


def test_make_remote_nao_copia_docs_memory_do_checkout():
    src = inspect.getsource(helpers.make_remote)
    assert "HIST" not in src, "make_remote voltou a ler o checkout (HIST)"


def test_make_remote_ignora_itens_vivos_no_checkout(tmp_path, monkeypatch):
    """Mesmo com um HIST cuja fila tem itens, o remoto de teste nasce com fila vazia."""
    fake = tmp_path / "fakehist"
    (fake / "docs/memory/handoffs/fila").mkdir(parents=True)
    (fake / "docs/memory/handoffs/fila/intruso.json").write_text('{"id": "intruso"}\n')
    monkeypatch.setattr(helpers, "HIST", fake)
    remote = make_remote(tmp_path / "r")
    t = remote_tree(tmp_path / "v", remote)
    assert not (t / "docs/memory/handoffs/fila/intruso.json").exists()
    assert git(t, "ls-files", "docs/memory/handoffs/fila") == "docs/memory/handoffs/fila/.gitkeep"

"""Regressão: sem caminhos absolutos de máquina; HIST = toplevel do checkout."""
from __future__ import annotations

import os, pathlib, re

from tests.p0a import helpers

# padrões montados em runtime para este arquivo não se auto-denunciar
_FRAGS = ("work" + "space", "home/" + "box", "data/data/com." + "termux")


def test_helpers_hist_e_code_sao_toplevel_do_checkout():
    top = helpers._repo_toplevel(pathlib.Path(__file__).resolve())
    assert helpers.HIST.resolve() == top.resolve()
    if not os.environ.get("FYAH_CODE_DIR"):
        assert helpers.CODE.resolve() == top.resolve()
    # não deve apontar para o path legado do box
    assert not str(helpers.HIST).endswith("/fyah") or helpers.HIST == top


def test_nenhum_caminho_absoluto_de_maquina_em_tests_nem_aimem():
    root = helpers._repo_toplevel(pathlib.Path(__file__).resolve())
    self_name = pathlib.Path(__file__).name
    pat = re.compile("|".join(re.escape("/" + f) if not f.startswith("home") else re.escape("/" + f) for f in _FRAGS))
    # padrões de máquina (montados em _FRAGS)
    pat = re.compile(r"/(?:workspace|home/box|data/data/com\.termux)(?:/|\b)")
    hits = []
    for base in (root / "tests", root / "aimem"):
        for p in base.rglob("*.py"):
            if "__pycache__" in p.parts or p.name == self_name:
                continue
            for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                s = line.lstrip()
                if s.startswith("#") or s.startswith('"""') or s.startswith("'''"):
                    continue
                if pat.search(line):
                    hits.append(f"{p.relative_to(root)}:{i}:{line.strip()[:120]}")
    assert not hits, "caminhos absolutos de máquina:\n" + "\n".join(hits[:20])

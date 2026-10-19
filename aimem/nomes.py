"""Charset único dos NOMES de arquivo que o aimem cria em docs/memory/ (fila, efeitos, sessoes, handoffs, raw).

Regra coerente do sistema (D):
- o aimem só CRIA nomes neste charset e falha alto (NomeInvalido) se um nome gerado sair dele — nada é
  criado-e-perdido;
- o gitsync SINCRONIZA qualquer nome válido para o git (porcelain -z + pathspec literal), inclusive arquivos
  postos por humanos com espaço/acento;
- a limpeza da prova (scripts/aimem_limpa_prova.py) só REMOVE nomes neste charset (mesma regex, conferida
  por teste) e o `registra` falha alto se o próprio run criar algo fora dele.
':' é permitido fora do 1º caractere (efeitos usam "<handoff_id>:<token>.json"); 1º caractere alfanumérico
evita dotfiles, '-' (opção) e ':' (magic de pathspec).
"""
from __future__ import annotations

import re

# \Z (não $): em Python `$` casa antes de um \n final — "x.md\n" passaria (achado D2).
SAFE_NAME_RE = r"^[A-Za-z0-9][A-Za-z0-9._:-]*\.(json|md)\Z"
SAFE_NAME = re.compile(SAFE_NAME_RE)
MAX_LEN = 200


class NomeInvalido(ValueError):
    pass


def valida_nome(name: str) -> str:
    """Retorna `name` se ok; levanta NomeInvalido caso contrário (nunca normaliza em silêncio)."""
    if not isinstance(name, str) or len(name) > MAX_LEN or not SAFE_NAME.fullmatch(name):
        raise NomeInvalido(f"nome de arquivo de memória fora do charset {SAFE_NAME_RE!r} (ou > {MAX_LEN}): {name!r}")
    return name

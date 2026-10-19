"""Isola os testes P0a do ambiente do runner.

Os remotos de teste usam `main`; como o sync não tem mais fallback implícito para main
(fail-closed), o destino é declarado explicitamente: AIMEM_SYNC_REF=main.
GITHUB_*/AIMEM_* herdados (ex.: GITHUB_REF_NAME/GITHUB_ACTIONS do CI) são removidos para
não vazar para os subprocessos. Testes que exercitam o destino montam o próprio env.
"""
import os

import pytest


@pytest.fixture(autouse=True)
def _env_sync_isolado(monkeypatch):
    for k in list(os.environ):
        if k.startswith(("GITHUB_", "AIMEM_")):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("AIMEM_SYNC_REF", "main")

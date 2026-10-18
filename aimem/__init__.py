"""AI Memory (akitaonrails/ai-memory) como harness MESTRE do E.R.

Hierarquia:
  ai-memory (servidor local, zero-LLM)            ← mestre: memória, sessões, handoffs
    └─ aimem.session (orquestrador fyah)          ← abre/fecha sessões, injeta briefing
         ├─ DeepSeek Harness + Qwen local (opcional, subordinado)
         ├─ er-analyze / scripts/er_analyze.py
         └─ python -m tools run …  (catálogo + pipelines; cada execução vira post-tool-use)
"""
from aimem.hooks import record_tool  # noqa: F401

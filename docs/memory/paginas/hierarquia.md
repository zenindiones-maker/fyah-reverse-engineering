# Hierarquia do harness

O **AI Memory** (akitaonrails/ai-memory, MIT) é o harness mestre. Todo o resto é subordinado a ele.

1. `ai-memory serve` (local, loopback, zero-LLM): guarda páginas, sessões e handoffs.
2. `python -m aimem` (orquestrador da Fyah): abre a sessão, recebe o handoff anterior (claim-once), entrega o briefing, roda o subordinado, registra `post-tool-use`, fecha a sessão e deixa um handoff novo.
3. Subordinados:
   - DeepSeek Harness + Qwen local (llama.cpp, CPU) — opcional, em `er-harness`.
   - `scripts/er_analyze.py` — em `er-analyze`.
   - `python -m tools run …` — catálogo e pipelines (`audio-full`, `video-full`, `apk-full`, `binary-inspect`). Cada execução vira um `post-tool-use` na sessão ativa.
   - `scripts/er_toolcheck.py` — checagem das ferramentas.
4. Memória durável: `docs/memory/` no git (o servidor do runner é efêmero e é reidratado com `python -m aimem seed`).

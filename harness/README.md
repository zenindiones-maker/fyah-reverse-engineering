# Harness E.R. × DeepSeek Harness (local, sem API de nuvem)

## Regras
- Sem API DeepSeek / token de nuvem / cadastro.
- GGUF Apache-2.0 ou MIT via llama.cpp na CPU do runner free (4 vCPU, 16 GB RAM).
- Cache de modelo ≤ ~10 GB (limite Actions).

## Presets
| preset | modelo | ~GB | notas |
|--------|--------|----:|-------|
| `fast` | Qwen2.5-0.5B-Instruct Q4 | 0.4 | opção rápida |
| `qwen25-7b` | Qwen2.5-7B-Instruct Q4 | 4.7 | meio-termo |
| `qwen25-14b` | Qwen2.5-14B-Instruct Q3_K_M | 7.3 | denso forte (default candidato) |
| `qwen3-14b` | Qwen3-14B Q3_K_M | 7.3 | Qwen3 denso |
| `qwen3-30b-a3b` | Qwen3-30B-A3B-Instruct IQ1_M | 9.7 | MoE ~3B ativos |
| `r1-14b` | R1-Distill-Qwen-14B Q3_K_M | 7.3 | MIT |

**Fora do orçamento:** gpt-oss-20b (~11.5 GB) e Qwen3-30B-A3B Q4 (~18 GB) — passam de 10 GB de cache e apertam disco/RAM.
**Qwen2.5-3B:** licença Research, não Apache.

Placeholder `LOCAL_LLM_KEY=local-no-cloud-key` (não é secret).


## Nota de bench
DSH+tools precisa de **ctx ≥ 8192** no llama-server; com 4096 o modelo devolve 1 token (`finish=length`). gpt-oss-20b (~11.5GB) fica fora do cache de 10GB.

## Resultado do bench (Actions, 4 vCPU/16 GB) — default = `qwen3-30b-a3b`
| preset | DSH rodou media-inspect + audio-full? | tempo DSH | decode |
|---|---|---|---|
| fast (0.5B) | só media-inspect | 10 s | ~60 tok/s |
| qwen25-7b Q4 | sim | 376 s | ~5–7 tok/s |
| qwen25-14b Q4 | sim (finish=completed) | 610 s | ~4–5 tok/s |
| **qwen3-30b-a3b TQ1_0 (MoE)** | **sim, tool_calls nativos** | **539 s** | ~4–12 tok/s |
| qwen3-14b / r1-14b | ctx 4k falhou; retest 8k cancelado | — | — |
gpt-oss-20b (~11.5 GB) não cabe no cache de 10 GB.

## Subordinado ao AI Memory (mestre)

Desde a v3.1.1 do [ai-memory](https://github.com/akitaonrails/ai-memory), o DeepSeek Harness **não é mais o chefe**. O `er-harness` sobe o ai-memory primeiro (`.github/actions/setup-aimemory`, zero-LLM) e roda o DSH dentro de uma sessão dele:

```
python -m aimem session --agent deepseek-harness --label dsh-<preset> --result out/harness.json -- python harness/run_dsh.py …
```

- O DSH recebe no começo da tarefa o briefing e o handoff anterior do ai-memory (`AIMEM_BRIEFING`).
- Cada `python -m tools run …` que o DSH executar vira `post-tool-use` na mesma sessão.
- No fim, o ai-memory deixa um handoff e o resumo vai para `docs/memory/`.
- O Qwen local continua **opcional**. Sem LLM nenhum, use o `er-aimemory`.

Detalhes e limitações: [docs/memory/README.md](../docs/memory/README.md).

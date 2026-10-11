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

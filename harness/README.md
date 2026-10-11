# Harness E.R. × DeepSeek Harness (local, sem API de nuvem)

## Regras
- **Sem API DeepSeek, sem token de nuvem, sem cadastro.**
- Modelos open-weights Apache-2.0 (GGUF Q4_K_M) via **llama.cpp** na CPU do runner.
- DSH fala com `http://127.0.0.1:8080/v1` via adapter **llm-pi-ai** (`openai-completions`).

## Presets (`MODEL_PRESET` / input `model`)
| preset | modelo | ~GGUF | uso |
|--------|--------|------:|-----|
| `fast` | Qwen2.5-0.5B-Instruct | 0.4 GB | rápido / fraco em tool-use |
| `qwen3-4b` | Qwen3-4B-Instruct-2507 | 2.5 GB | padrão candidato (qualidade/tempo) |
| `qwen25-7b` | Qwen2.5-7B-Instruct | 4.7 GB | mais forte, mais lento |
| `qwen3-8b` | Qwen3-8B | 5.0 GB | apertado em 16 GB RAM |

**Qwen2.5-3B-Instruct foi pulado:** licença *Qwen Research*, não Apache-2.0.

Registro: `harness/models.json`.

## Placeholder ≠ API key
O cliente OpenAI-compatible do pi-ai **exige** um header `Authorization`. Usamos
`LOCAL_LLM_KEY=local-no-cloud-key` (hardcoded). O llama.cpp ignora o valor. **Não há secret no GitHub.**

## Uso
```bash
MODEL_PRESET=qwen3-4b bash harness/run_local_llm.sh   # terminal 1
MODEL_PRESET=qwen3-4b python harness/run_dsh.py \
  --model-preset qwen3-4b \
  --task "Inspecione a mídia e rode audio-full" \
  --file-url 'https://…'
```

Workflow: `er-harness.yml` (choice `model`). Score de tool-use em `out/score.json` **antes** do fallback direto das tools.

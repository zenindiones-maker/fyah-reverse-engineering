# Harness E.R. × DeepSeek Harness (local, sem API de nuvem)

## Regras
- **Sem API DeepSeek, sem token de nuvem, sem cadastro.**
- Modelo open-weights (Qwen2.5-0.5B-Instruct GGUF, Apache-2.0) servido por **llama.cpp** na CPU do runner.
- DSH fala com `http://127.0.0.1:8080/v1` via adapter **llm-pi-ai** (`openai-completions`).

## Placeholder ≠ API key
O cliente OpenAI-compatible do pi-ai **exige** um header `Authorization`. Documentação oficial:

> *a keyless local server needs a placeholder credential referenced by `apiKeyEnv`*

Usamos `LOCAL_LLM_KEY=local-no-cloud-key` (hardcoded no workflow). O llama.cpp ignora o valor. **Não há secret no GitHub.**

## Por que não dá para usar só `DEEPSEEK_BASE_URL`
O profile `sdk-minimal` monta `dsh-llm-deepseek-api-key`, que fala **Anthropic Messages** (`/v1/messages`), não Chat Completions. llama.cpp/Ollama falam OpenAI Chat Completions — por isso o patch `local-llm.patch.yml` remove o adapter DeepSeek e insere `llm-pi-ai`.

## Uso
```bash
# terminal 1
bash harness/run_local_llm.sh
# terminal 2
pip install deepseek-harness-sdk
python harness/run_dsh.py --task "Inspecione a mídia" --file-url 'https://…'
```

Workflow: `er-harness.yml`.


## Status no Actions
- llama.cpp CPU + Qwen2.5-0.5B GGUF sobe e responde em `/v1/models`.
- DSH `sdk-minimal` + patch `llm-pi-ai` completa um turno com `ok: true` **sem chave de nuvem** (só placeholder `LOCAL_LLM_KEY`).
- Modelos 0.5B são fracos em tool-use; o workflow também roda `python -m tools run media-inspect` diretamente para garantir resultado útil.

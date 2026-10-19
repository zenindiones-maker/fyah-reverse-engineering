# Memória do E.R. — AI Memory como harness mestre

O [AI Memory](https://github.com/akitaonrails/ai-memory) (MIT, versão **3.1.1**) é o **harness mestre** do repositório. Todo o resto trabalha **subordinado** a ele: DeepSeek Harness (com Qwen local, opcional), `er-analyze`, `er-toolcheck`, as ferramentas do catálogo (`python -m tools`) e os pipelines.

## Regras

- **Custo zero, open source, CPU no GitHub Actions.**
- **Zero LLM:** o servidor sobe sem nenhum provedor de LLM (`llm: disabled`). Captura, busca (FTS5) e handoffs funcionam sem modelo; o resumo de cada sessão é feito por heurística (`M3, no-LLM heuristic`).
- **Sem API, sem token de nuvem, sem cadastro.** O `ai-memory init` gera sozinho uma senha aleatória local dentro da pasta temporária do runner. Ela não é chave de API, não tem conta, não sai da máquina e some quando o job acaba.
- **Nenhum binário no repo:** o binário vem do release oficial (`ai-memory-linux-x86_64.tar.gz`, sha256 conferido) e fica no cache do Actions (`.github/actions/setup-aimemory`).

## Hierarquia

```
ai-memory serve (127.0.0.1:49374, zero-LLM)      ← MESTRE: páginas, sessões, handoffs
└─ python -m aimem (orquestrador Fyah)           ← abre sessão, entrega briefing/handoff, fecha
   ├─ er-harness  → DeepSeek Harness + Qwen3-30B-A3B local (llama.cpp, CPU) — agente subordinado
   ├─ er-analyze  → scripts/er_analyze.py
   ├─ er-toolcheck→ scripts/er_toolcheck.py (as 92 ferramentas)
   └─ er-aimemory → python -m tools run … (catálogo + pipelines)
        cada `python -m tools run` vira um `post-tool-use` na sessão ativa (aimem/hooks.py)
```

Ciclo de cada sessão:
1. `setup-aimemory` sobe o servidor e roda `python -m aimem seed`: as páginas de `paginas/`, as últimas sessões de `sessoes/` e o handoff aberto (`handoffs/aberto.json`) voltam pro servidor.
2. `python -m aimem session` pega o handoff anterior (claim-once) e o briefing do projeto, e entrega ao subordinado (`AIMEM_BRIEFING`; o DSH recebe isso no começo da tarefa).
3. Eventos `session-start` → `user-prompt-submit` → `post-tool-use` (um por ferramenta) → `session-end` vão para `POST /hook/batch`, com `extension=fyah.er` e `ingest_key` estável.
4. No fim, um handoff tipado (`memory_handoff_begin`: resumo, próximos passos, perguntas em aberto, arquivos) e o resumo sem LLM são gravados aqui e commitados por `scripts/aimem_commit.sh`.

## Pastas

| Pasta | O que tem |
|---|---|
| `paginas/` | Conhecimento fixo do projeto (regras, hierarquia, como rodar). Editável à mão. |
| `sessoes/` | Uma página por sessão: comando, resultado, handoff deixado e o resumo do ai-memory. |
| `handoffs/` | Handoffs em markdown + `aberto.json`, o "bastão" que a próxima execução recebe. |

## Comandos

```bash
python -m aimem seed                      # docs/memory → servidor
python -m aimem smoke                     # captura + busca + handoff, sem LLM
python -m aimem run-tool media-inspect --input URL --out out/media-inspect.json
python -m aimem session --agent fyah-er --label rotulo --result out/x.json -- comando ...
python -m aimem status                    # handoffs abertos
```

## Limitação documentada (`ai-memory run`)

`ai-memory run` só lança harnesses de agente que ele conhece: `claude`, `codex`, `opencode`, `opencode2`, `pi`, `crush`, `omp`, `kimi`, `command-code`, `kiro`, `grok`, `antigravity` e `copilot`. Um valor diferente (como o nosso catálogo ou o DeepSeek Harness) dá `invalid value … for harness`, e ele não embrulha comandos arbitrários. Além disso, esses harnesses dependem de LLM de nuvem.

Por isso usamos o caminho **zero-LLM** que o próprio ai-memory documenta para orquestradores externos (`docs/external-lifecycle.md` e `docs/programmatic-memory.md`):
- **Captura externa:** `POST /hook/batch` com `AI_MEMORY_CAPTURE_OWNER=fyah.er`.
- **Memória e handoff:** pelo MCP HTTP (`memory_write_page`, `memory_query`, `memory_briefing`, `memory_handoff_begin/accept`).
- **Markdown no git**, como fonte durável.

Agentes que não estão na lista nativa aparecem como `agent: other` nas páginas do ai-memory. O agente lógico (`deepseek-harness`, `fyah-tools`, `er-analyze` ou `er-toolcheck`) fica registrado aqui, como o guia de captura externa recomenda.

## Fila durável (`handoffs/fila/`) — P0a

Cada handoff é um arquivo `fyah-handoff@1` com estados `pending|claimed|consumed|failed`.
O bastão **não** vive mais só em `aberto.json` (legado: migrar com `python -m aimem migrate`).
Efeitos idempotentes: `handoffs/efeitos/`. Cópias brutas de migração/recuperação: `handoffs/raw/`.
Commit da memória: `scripts/aimem_commit.sh` → `python -m aimem sync` (sem `-X theirs`; falha = artefato em `out/aimem/conflito/`).

Recuperação do handoff perdido do toolcheck (`4a0ec59` sobrescrito em `4ffade0`):

```bash
python -m aimem recover --commit 4a0ec59 --overwritten-by 4ffade0 --by "E.R."
bash scripts/aimem_commit.sh recuperacao-toolcheck
```

Rodar isso no Actions na branch de validação (não no commit de código), para a prova ser contra o histórico real do remoto.

## Workflow `er-memory-persist` (branch `p0a-fila-handoffs`)

Gatilhos: `workflow_dispatch` e `push` (paths: workflow, `aimem/**`, `scripts/aimem_commit.sh`, `tests/p0a/**` — **sem** `docs/memory/**`).

`docs/memory/**` fica fora do filtro **de propósito**: commits de memória — feitos por bot ou por humano —
não devem disparar a validação; só mudanças de código/teste/workflow disparam.

Pushes feitos com o `GITHUB_TOKEN` do Actions **não** disparam novos runs deste workflow
([documentação oficial](https://docs.github.com/en/actions/using-workflows/triggering-a-workflow#triggering-a-workflow-from-a-workflow)).

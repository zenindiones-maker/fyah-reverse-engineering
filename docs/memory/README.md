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
1. `setup-aimemory` sobe o servidor e roda `python -m aimem seed`: as páginas de `paginas/` e as últimas sessões de `sessoes/` (exceto páginas de sessão de **prova**) voltam pro servidor. `handoffs/*.md`, `aberto.json` e a fila **não** são enviados como página; o handoff chega só pelo claim da fila (passo 2).
2. `python -m aimem session` pega o handoff anterior (claim-once) e o briefing do projeto, e entrega ao subordinado (`AIMEM_BRIEFING`; o DSH recebe isso no começo da tarefa).
3. Eventos `session-start` → `user-prompt-submit` → `post-tool-use` (um por ferramenta) → `session-end` vão para `POST /hook/batch`, com `extension=fyah.er` e `ingest_key` estável.
4. No fim, um handoff tipado (`memory_handoff_begin`: resumo, próximos passos, perguntas em aberto, arquivos) e o resumo sem LLM são gravados aqui e commitados por `scripts/aimem_commit.sh`.

## Pastas

| Pasta | O que tem |
|---|---|
| `paginas/` | Conhecimento fixo do projeto (regras, hierarquia, como rodar). Editável à mão. |
| `sessoes/` | Uma página por sessão: comando, resultado, handoff deixado e o resumo do ai-memory. |
| `handoffs/` | Handoffs em markdown (registro humano), `fila/` (o bastão durável), `efeitos/`, `raw/` e o legado `aberto.json`. |

## Comandos

```bash
python -m aimem seed                      # docs/memory → servidor
python -m aimem smoke                     # captura + busca + handoff, sem LLM
python -m aimem run-tool media-inspect --input URL --out out/media-inspect.json
python -m aimem session --agent fyah-er --label rotulo --result out/x.json -- comando ...
python -m aimem status                    # fila + handoffs (cada item com "eh_prova")
python -m aimem fila --json               # itens da fila; "eh_prova": true = prova, nunca entregue a consumidor
```

### Destino do push da memória (fail-closed)

`python -m aimem sync` / `scripts/aimem_commit.sh` (e `session`, quando grava efeitos) **não têm fallback para `main`**.
- **No Actions:** o destino é `GITHUB_REF_NAME` (a branch do run). Workflows disparados em `main` continuam gravando em `main`.
- **Fora do Actions (uso local): `AIMEM_SYNC_REF` é obrigatório.** Exemplo:

```bash
AIMEM_SYNC_REF=p0a-fila-handoffs bash scripts/aimem_commit.sh minha-sessao
# ou
export AIMEM_SYNC_REF=main && python -m aimem sync --msg "memoria: ..."
```

O sync falha (código ≠ 0, sem nenhum `git push`, dados locais preservados) se: nenhum dos dois estiver definido;
`GITHUB_ACTIONS=true` sem `GITHUB_REF_NAME`; `AIMEM_SYNC_REF` ≠ `GITHUB_REF_NAME`; o nome de branch for inválido
(`git check-ref-format --branch`, sem espaços, `+`, `:` ou prefixo `refs/`); ou `AIMEM_FORBID_MAIN=1` e o alvo for
`main` em qualquer grafia (`MAIN`, `refs/heads/main`, `+main`, `HEAD:main`…). Regressão: `tests/p0a/test_p0a_forbid_main.py`.

## Limitação documentada (`ai-memory run`)

`ai-memory run` só lança harnesses de agente que ele conhece: `claude`, `codex`, `opencode`, `opencode2`, `pi`, `crush`, `omp`, `kimi`, `command-code`, `kiro`, `grok`, `antigravity` e `copilot`. Um valor diferente (como o nosso catálogo ou o DeepSeek Harness) dá `invalid value … for harness`, e ele não embrulha comandos arbitrários. Além disso, esses harnesses dependem de LLM de nuvem.

Por isso usamos o caminho **zero-LLM** que o próprio ai-memory documenta para orquestradores externos (`docs/external-lifecycle.md` e `docs/programmatic-memory.md`):
- **Captura externa:** `POST /hook/batch` com `AI_MEMORY_CAPTURE_OWNER=fyah.er`.
- **Memória e handoff:** pelo MCP HTTP (`memory_write_page`, `memory_query`, `memory_briefing`, `memory_handoff_begin/accept`).
- **Markdown no git**, como fonte durável.

Agentes que não estão na lista nativa aparecem como `agent: other` nas páginas do ai-memory. O agente lógico (`deepseek-harness`, `fyah-tools`, `er-analyze` ou `er-toolcheck`) fica registrado aqui, como o guia de captura externa recomenda.

## Limitação documentada (proteção de `main` no GitHub)

Hoje `main` **não tem** proteção de branch nem ruleset no GitHub (`branches/main` → `protected: false`; rulesets → `[]`; lido em 2026-10-18 e de novo em 2026-10-19).
As travas contra escrita em `main` (refspec `HEAD:refs/heads/<ref>`, destino fail-closed, `AIMEM_FORBID_MAIN`, guards do
`er-memory-persist`) são **só de código/workflow**: protegem os caminhos que passam por `aimem`, mas **não substituem**
proteção do lado do GitHub (qualquer outro push com permissão de escrita em `main` continua possível).

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

Gatilhos: `workflow_dispatch` e `push` na branch `p0a-fila-handoffs`, só com mudança em: o próprio workflow, `aimem/**`,
`scripts/aimem_commit.sh`, `scripts/aimem_limpa_prova.py`, `pyproject.toml` e `.github/actions/setup-aimemory/**`.

Ficam **fora** do filtro de propósito:
- `docs/memory/**`: commits de memória (de bot ou de humano) não devem disparar a validação;
- `tests/p0a/**`: este workflow não roda pytest (quem roda é o `ci.yml`), e cada run grava itens de prova na branch.

Pushes feitos com o `GITHUB_TOKEN` do Actions **não** disparam novos runs deste workflow
([documentação oficial](https://docs.github.com/en/actions/using-workflows/triggering-a-workflow#triggering-a-workflow-from-a-workflow)).

Jobs: `job-a` cria um handoff de prova conhecido e registra o manifesto A. `job-b` consome exatamente esse ID (claim
por ID) e faz o manifesto final. `job-c` confere tudo no remoto, testa o recover (2×, idempotente) e roda a **limpeza
em dry-run**. Manifesto e relatório do dry-run viram artefatos do run.

## Isolamento da prova (D2)

Os itens que o `er-memory-persist` grava são **prova**, não memória do projeto. Regras:

- **Marca:** item novo de prova tem `kind: "prova"` e `prova: {workflow, run_id, run_attempt}`. Item legado sem marca
  (ex.: `…-04d891.json`, gravado pelo P0a antes do D2) é reconhecido pela origem: `origin.workflow == "er-memory-persist"`.
- **Claim:** `claim_one` (claim normal de consumidor) **nunca** pega item de prova. A checagem roda na listagem e de
  novo dentro do CAS, contra o estado mais novo do remoto. `claim_id` só aceita item de prova se o workflow e o
  `run_id` forem os mesmos do run que o criou. Fora isso, o claim é `lost` e nada é escrito.
- **IDs:** `AIMEM_CLAIM_ID` passa pelo validador de nome antes de qualquer leitura. Um arquivo da fila cujo `id`
  interno não bate com um arquivo `fila/<id>.json` válido não é oferecido.
- **Hidratação:** o `seed` não envia páginas de sessão de prova (marca, ou primeira linha `# Sessão … (er-memory-persist)`)
  e nunca envia `handoffs/*.md`. `pending_handoffs` exclui prova.
- **Listagem:** `status` e `fila --json` mostram `"eh_prova": true|false` em cada item.
- **Preservação:** nada disso apaga ou altera o item de prova. Ele fica no git, `pending`, e só sai pela limpeza manual (abaixo).

Regressões:
- `tests/p0a/test_p0a_prova_isolada.py`;
- `tests/p0a/test_p0a_consumidores_reais_19de0b7.py`: os 4 consumidores em sequência contra dois estados, ambos
  tirados do objeto git `19de0b7` (o `docs/memory` publicado na `p0a-fila-handoffs`):
  - o `docs/memory` inteiro de `19de0b7` (árvore `0445557e…`, 30 arquivos), com as provas legadas;
  - o mesmo sem as 3 provas legadas (04d891, `persist-prova-a-39190430768-1.json` e o efeito dele), removidas no
    teste e conferidas pela árvore `85abd05f…` (27 arquivos).

  Esse teste precisa do histórico completo (`fetch-depth: 0`) e falha se o objeto `19de0b7` não existir.

## Nomes de arquivo de memória (D2)

Há um validador único, `aimem/nomes.py`: `^[A-Za-z0-9][A-Za-z0-9._:-]*\.(json|md)\Z`, no máximo 200 caracteres,
sem `/`, sem espaço e sem quebra de linha. O `scripts/aimem_limpa_prova.py` usa a mesma regra.

- **Criação** (`ledger.save`, efeitos, `prova-item`, migrate, recover, `session`): o nome é validado **antes** de criar
  qualquer arquivo **ou diretório**. Nome inválido levanta `NomeInvalido` e nada é criado.
- **Limpeza:** aceita exatamente o mesmo conjunto que a criação.
- **Sincronização (`gitsync`):** é um superconjunto de propósito. Sincroniza qualquer arquivo de `docs/memory`,
  inclusive arquivos com nome humano, para não perder memória escrita à mão. Tudo o que a criação aceita, o sync leva.
- O YAML dos workflows não escreve arquivo de memória direto; só via `python -m aimem`.

## Limpeza da prova (dry-run no Actions; exclusão real só manual)

No Actions, `scripts/aimem_limpa_prova.py limpa` roda **sempre sem `--confirmar`**, ou seja, em dry-run. Ele valida o
manifesto (sha256, commit de criação e trailers do run) e só relata o que **seria** removido. Nenhum passo de YAML
passa `--confirmar`, e nenhum caminho automatizado apaga arquivo.

Exclusão real, só por um humano e só depois de revisar o relatório do dry-run (artefato
`prova-limpeza-dry-run-<run>-<attempt>`):

```bash
# num clone limpo e atualizado da branch p0a-fila-handoffs
git fetch origin p0a-fila-handoffs && git switch p0a-fila-handoffs && git merge --ff-only origin/p0a-fila-handoffs
sha256sum manifesto.json                                   # tem que bater com o manifesto.sha256 do artefato
S=scripts/aimem_limpa_prova.py; R=origin/p0a-fila-handoffs
python "$S" snapshot --ref "$R" --out antes.json
python "$S" limpa --manifest manifesto.json --manifest-sha256 <SHA256> --run-base <RUN_BASE> --ref "$R" \
  --workflow er-memory-persist --run-id <RUN_ID> --attempt <ATTEMPT> --relatorio dry.json          # 1º: dry-run
python "$S" limpa --manifest manifesto.json --manifest-sha256 <SHA256> --run-base <RUN_BASE> --ref "$R" \
  --workflow er-memory-persist --run-id <RUN_ID> --attempt <ATTEMPT> --confirmar <SHA256> --relatorio real.json
git status --porcelain -- docs/memory                      # só os caminhos do manifesto podem aparecer como removidos
AIMEM_SYNC_REF=p0a-fila-handoffs bash scripts/aimem_commit.sh limpeza-prova-<RUN_ID>
git fetch origin p0a-fila-handoffs
python "$S" verifica --esperado removido --antes antes.json --manifest manifesto.json --manifest-sha256 <SHA256> --ref "$R"
```

Rode tudo na raiz do clone, porque os caminhos do manifesto são relativos. Se `--confirmar` não bater com o sha256 do
manifesto, sai com rc=1 sem apagar nada. `--dry-run` força o dry-run. A sequência snapshot → limpa --confirmar →
commit → verifica é exercitada em `tests/p0a/test_p0a_limpa_prova.py::test_positivo_remove_so_manifesto_e_resto_byte_a_byte`.
O manifesto só lista arquivos criados pelo próprio run. Os itens de prova legados, sem manifesto, **não** entram na
limpeza automática: `fila/20261019T023307Z-39190430768-1-04d891.json`, `fila/persist-prova-a-39190430768-1.json`, o
efeito `efeitos/persist-prova-a-39190430768-1:0e5ce265….json` e as duas `.md` `prova-b-277e23`. Eles ficam no git
byte a byte e isolados (seção anterior), e removê-los é uma decisão humana à parte.

## Recuperação (rollback)

- **Código:** `git revert <sha>` do commit problemático, num commit novo, sem `--force` e sem reescrever histórico.
  O revert do commit de isolamento da prova (D2) volta ao commit anterior (limpeza por manifesto), que **entrega
  prova a consumidor**. Só reverta se também for parar os consumidores
  (`er-analyze`, `er-toolcheck`, `er-harness`, `er-aimemory`) na branch.
- **Memória:** cada sync é um commit separado em `docs/memory/`, então dá para reverter um commit de memória isolado.
  Conflito de sync vira artefato em `out/aimem/conflito/` e não força nada.
- **Handoff perdido:** `python -m aimem recover` (seção "Fila durável").

## Limitações (D2)

- Nada do D2 foi provado ainda no **Actions real**. A validação foi local (pytest, simulação E2E do YAML, actionlint e
  shellcheck).
- `main` sem proteção nem ruleset (acima). As travas são só de código.
- O servidor de teste (`tests/p0a/fakeserver.py`) devolve um briefing fixo. A garantia de hidratação vem do que é
  **enviado** ao servidor (`memory_write_page`), não do briefing do ai-memory real.
- Trailers de commit (`Aimem-Workflow`, `Aimem-Run-Id`, `Aimem-Run-Attempt`, `Aimem-Job`) identificam o run, mas não autenticam: quem tem write no repo pode forjá-los.

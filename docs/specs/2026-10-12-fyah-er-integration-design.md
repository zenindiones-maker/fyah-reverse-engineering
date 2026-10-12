# Fyah Reverse Engineering — plano de integração verificável

Data: 2026-10-12  
Branch de trabalho: `work/fyah-er-integration-hardening-v1`  
Base preservada: `69395b21dcf1f36bc1e708b427f623220b971bb7` (`feat/rea-mcp-integration-v1`)

## Objetivo

Evoluir o Fyah Reverse Engineering de um conjunto de ferramentas e workflows para uma plataforma de investigação reproduzível, com execução uniforme, encadeamento explícito, segurança por padrão e evidências verificáveis. Preservar a política de custo zero, ferramentas abertas, execução local/Actions e análise apenas de artefatos próprios, licenciados ou autorizados. Não misturar responsabilidades com outros projetos.

## Estado verificado na base

- O catálogo `tools/catalog.py` lista 12 ferramentas; inclui quatro pipelines e ferramentas de áudio, vídeo, APK e utilitários.
- `tools/__main__.py` implementa um executor, mas faz download HTTP sem limite explícito de bytes/tempo total, não aplica política comum de hash/artefato e depende de lógica específica por ferramenta.
- `fyah_re_cli.py` é um placeholder que retorna sucesso, portanto não é uma CLI operacional.
- `scripts/er_analyze.py` duplica a lógica de despacho dos workflows e do catálogo; as escolhas de dependências não são centralizadas.
- `pyproject.toml` separa extras por domínio, mas os requisitos reais dos pipelines e seus extras/venvs precisam ser reconciliados automaticamente.
- Os testes existentes cobrem análises específicas e um teste de smoke da CLI ainda codifica o comportamento placeholder.
- O E2E Qwen3 + REA MCP foi concluído em 2026-10-12 no run [38270283076](https://github.com/zenindiones-maker/fyah-reverse-engineering/actions/runs/38270283076): `model_proposed=true`, `policy_approved=true`, `executed=true`, retorno 0; ferramenta `inspect_artifact` retornou `PASS`, relatório de 5618 caracteres e SHA-256 de fixture `de9ca171a8f333e1df312f926c9778ac25853322f2afc8df81ecbdebafcb0100`. Isso prova esse caminho e essa fixture, não a integração universal do arsenal.

## Princípios arquiteturais

1. **Uma fonte de verdade:** catálogo declarativo com nome, domínio, versão de contrato, invocação, dependências, entradas, saídas, capacidades e limites.
2. **CLI real:** `fyah-re` deve listar capacidades, validar entradas, executar ferramentas/pipelines, produzir saída estruturada e devolver exit codes coerentes. Nenhum placeholder pode terminar em sucesso.
3. **Execução rastreável:** cada execução gera um recibo versionado com ID, timestamp UTC, ferramenta e versão, hash SHA-256 de cada entrada local obtida, parâmetros sanitizados, estado, duração, artefatos de saída, erros e proveniência. Segredos, URLs assinadas e conteúdo sensível não devem ser registrados sem necessidade.
4. **Fail-closed:** entradas inválidas, ferramenta não permitida, falta de dependência, timeout, limite excedido ou resultado inválido terminam como falha explícita; fallback não conta como sucesso do modelo/ferramenta primária.
5. **Limites no ponto de entrada:** esquema de URL, limite de bytes, timeout, diretório temporário controlado, validação de caminho, limpeza de temporários e execução de subprocessos sem shell.
6. **Orquestração por dados:** planos de múltiplas etapas usam nomes de ferramentas permitidos e referências a artefatos produzidos por etapas anteriores; sem comandos arbitrários gerados pelo modelo.
7. **Separação de autoridade:** Qwen/DSH pode propor análises; política determinística autoriza; executor realiza; validador independente confere saída. REA MCP é um adaptador e não autoridade global.
8. **Compatibilidade incremental:** manter as interfaces atuais `python -m tools run ...` e workflows durante migração; remover duplicação somente depois de testes de paridade.
9. **Custo e licenças:** sem API paga, tokens externos, serviços novos ou dependências de licença incompatível. Ferramentas opcionais indisponíveis são reportadas como tais, não simuladas.

## Fases e critérios de aceite

### Fase 1 — Inventário e contrato comum

- Gerar um inventário derivado do código: módulo/invocação, extras/venv, executabilidade, entradas, saídas e testes associados.
- Verificar que cada item do catálogo aponta para um módulo ou executor existente; itens apenas documentados devem ser rotulados como planejados/parciais, nunca como disponíveis.
- Implementar contrato de resultado e recibo versionados com sucesso/falha explícitos.
- Adicionar testes de regressão antes de alterar comportamento: CLI placeholder, ferramenta desconhecida, URL inválida, limite de download, falha de subprocesso, JSON de saída inválido e geração do recibo.
- Critério: testes focados e suite completa passam; relatório de inventário reproduzível; nenhuma ferramenta não executável aparece como operacional.

### Fase 2 — Núcleo de execução e segurança

- Centralizar resolução de dependências e validação de parâmetros no catálogo.
- Reutilizar o executor tanto na CLI como em workflows, sem duplicar regras.
- Aplicar limites configuráveis, timeouts, hash, temporários isolados e limpeza.
- Critério: mesmas entradas produzem contrato de saída equivalente no CLI e no workflow; testes negativos comprovam falha fechada.

### Fase 3 — Orquestração

- Introduzir um plano de execução versionado, validado contra allowlist e DAG acíclico.
- Transferir saídas entre etapas por referências a artefatos, não por texto livre.
- Preservar estado parcial explicitamente: etapas concluídas, falhas, etapas bloqueadas e artefatos válidos.
- Critério: um E2E combina ao menos duas ferramentas reais compatíveis, verifica os artefatos e demonstra que uma falha de etapa não é mascarada.

### Fase 4 — Inteligência e REA MCP

- Manter decisão do modelo isolada da execução.
- Validar saída de decisão com esquema estrito e política independente.
- Registrar proposta, decisão, chamada efetiva, fixture/artefato, hashes e resposta do MCP.
- Critério: E2E de aprovação e negação, chamada inválida, MCP indisponível e tentativa de escapar da fixture; nenhuma chamada fora da allowlist.

### Fase 5 — Evidências e regressão contínua

- Criar resumo final com hipóteses, ferramentas, versões, hashes, métricas, limites e conclusões.
- Integrar testes de contrato, unitários, integração e E2E aos workflows.
- Critério: artefato verificável por run, sem credenciais, com digest publicado e resultado coerente com os exit codes.

## Ordem de implementação

Começar na Fase 1, em commits pequenos e isolados, sobre esta branch de trabalho. Não modificar nem fazer merge da PR #1 automaticamente. Não alterar a branch `main` diretamente. Cada etapa só avança quando os testes e evidências da etapa atual sustentarem a conclusão.

## Decisões externas e limites

- A primeira versão do executor mantém CLI e GitHub Actions como interfaces suportadas; não introduz servidor persistente.
- Artefatos grandes não devem ser copiados para o recibo; o recibo registra caminho relativo, tamanho e hash.
- Uma execução composta pode retornar estado `partial` somente se o contrato o definir explicitamente; a CLI retorna código diferente de zero se uma etapa obrigatória falhar.
- Não executar automaticamente binários desconhecidos fora de sandbox. Inspeção estática e execução dinâmica permanecem capacidades separadas e autorizadas.

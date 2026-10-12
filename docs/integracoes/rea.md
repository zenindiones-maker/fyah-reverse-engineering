# REA — Reverse Engineer Anything (integração opcional)

Fonte oficial: https://github.com/morluto/rea
Pacote oficial: https://www.npmjs.com/package/rea-agents
Licença upstream: MIT. O projeto **não copia** o código-fonte do REA.

## Escopo e governança

O REA é um servidor MCP e CLI para análise autorizada de aplicações, JavaScript/Electron, .NET e binários. Não substitui o DeepSeek Harness nem recebe autoridade para modificar BR-no-GTA ou Hazewave. Cada integração deve ser autorizada no respectivo projeto. Não utilizar para DRM ou material de terceiros sem autorização.

## Requisitos

Node.js 22.19+ (ou 24.11+), npm e, somente para análise nativa, uma ferramenta compatível como Ghidra/Hopper/IDA previamente aprovada. Análise estática JavaScript não requer mecanismo nativo. Não instalar Hopper automaticamente; não aceitar licença paga.

## Instalação em ambiente efêmero de desenvolvimento

1. Inspecionar o pacote e fixar uma versão auditada de `rea-agents` antes da instalação persistente.
2. Rodar `npx rea-agents@<VERSAO_AUDITADA> setup` em terminal do ambiente autorizado, revisar as alterações propostas e aprovar apenas o MCP e agente necessários.
3. Reiniciar o cliente MCP, conferir ferramentas registradas e executar um caso de teste autorizado com evidências reais.
4. Não salvar configurações com tokens, credenciais, caminhos privados ou dados analisados no repositório.

A instalação da **skill** (`npx skills add https://github.com/morluto/rea --skill reverse-engineer-anything`) não instala nem registra o servidor MCP. Setup e skill são passos distintos.

## Teste isolado em GitHub Actions

O workflow `rea-smoke.yml` é manual e somente verifica o pacote e a CLI num runner Linux temporário. Não registra MCP, não instala Hopper/Ghidra, não executa análises e não altera outros repositórios. Para integração efetiva com um agente, usar um ambiente com suporte a MCP e executar o setup aprovado.

## Critérios de aceite

- Versão, origem, licença e dependências verificadas.
- CLI executa e retorna código zero em ambiente isolado.
- Registro MCP demonstrado em agente autorizado, com ferramentas enumeradas.
- Análise autorizada produz evidência rastreável e limitações explícitas.
- Nenhum recurso pago, alteração em outro repositório ou token exposto.

**Estado inicial:** configuração versionada; instalação real e prova E2E dependem de executar o workflow e aprovar o setup no ambiente do agente.

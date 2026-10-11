# Máquina custo zero do E.R.

Como o E.R. trabalha sem PC e sem gastar nada. Controle total pelo celular (app GitHub → Actions → Run workflow).

## Arquitetura
1. **Cérebro:** a máquina na nuvem do Grok Bot pesquisa, escreve código, faz commits e dispara workflows.
2. **Músculo CPU:** GitHub Actions neste repo **público** (minutos ilimitados e grátis; 4 vCPU/16 GB/~14 GB de disco; job até 6 h; cache 10 GB).
3. **Sem GPU externa:** tudo em CPU; modelos pesados em trechos curtos. Pesos públicos baixados anonimamente e guardados no `actions/cache`.
4. **Vitrine:** GitHub Pages para docs (mesma conta, sem serviço extra).

## Workflows
| Workflow | Quando | O que faz |
|---|---|---|
| `er-analyze` | manual | ponto único: escolha a ferramenta (audio-profile, compare, media-inspect, cuts-pacing, stems) e cole a URL |
| `er-daily` | dias úteis 09:00 BRT + manual | repos open source atualizados + arXiv (áudio/MIR/vídeo/RE) → `docs/diario/AAAA-MM-DD.md` |
| `catalog-refresh` | mensal + manual | catálogo completo em `docs/catalogo/` |
| `ci` | push/PR | testes |

## Sem API, sem token, sem cadastro
Nenhum workflow usa secrets. O único token é o `GITHUB_TOKEN` automático do próprio Actions (não precisa criar nada). Nenhuma ferramenta exige conta, chave de API ou cadastro em outro serviço.

## Regras da máquina
- Nunca adicionar cartão nem usar runners maiores (são sempre pagos).
- **Nunca commitar binários de terceiros** nem mídia analisada; entradas chegam por URL e saem como artefato temporário.
- Só material próprio, licenciado ou de domínio público; sem DRM.
- Opções descartadas por custo ou fim do plano grátis: larger runners, Gitpod, Firebase Studio, créditos AWS. Oracle Always Free só com cartão (fora da regra por padrão).

## Ferramentas instaladas (custo zero)
- Ação reutilizável `.github/actions/setup-er`: Python, apt (ffmpeg, mediainfo, radare2, apktool, Java), extras do `pyproject.toml` e, opcionalmente, jadx e Ghidra baixados das **releases oficiais** em tempo de execução (com cache; nenhum binário entra no repo).
- Extras: `[audio]`, `[audio-plus]`, `[ml]`, `[video]`, `[apps]`, `[formats]`, `[binary]`, `[all]`.
- `er-toolcheck` (manual + domingo): instala tudo e testa cada ferramenta → [ferramentas/STATUS.md](ferramentas/STATUS.md).

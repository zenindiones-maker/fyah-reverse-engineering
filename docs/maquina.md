# Máquina custo zero do E.R.

Como o E.R. trabalha sem PC e sem gastar nada. Controle total pelo celular (app GitHub → Actions → Run workflow).

## Arquitetura
1. **Cérebro:** a máquina na nuvem do Grok Bot pesquisa, escreve código, faz commits e dispara workflows.
2. **Músculo CPU:** GitHub Actions neste repo **público** (minutos ilimitados e grátis; 4 vCPU/16 GB/~14 GB de disco; job até 6 h; cache 10 GB).
3. **Músculo GPU:** Kaggle Notebooks (GPU P100 ou 2×T4, ~30 h/semana, sessão até 12 h) via `er-gpu-kaggle`. Colab grátis como reserva.
4. **Vitrine:** Hugging Face Hub (modelos/datasets grátis) e GitHub Pages para docs.

## Workflows
| Workflow | Quando | O que faz |
|---|---|---|
| `er-analyze` | manual | ponto único: escolha a ferramenta (audio-profile, compare, media-inspect, cuts-pacing, stems) e cole a URL |
| `er-daily` | dias úteis 09:00 BRT + manual | repos open source atualizados + arXiv (áudio/MIR/vídeo/RE) → `docs/diario/AAAA-MM-DD.md` |
| `er-gpu-kaggle` | manual | envia `kaggle/<job>/` ao Kaggle com GPU, espera e baixa o output como artefato |
| `catalog-refresh` | mensal + manual | catálogo completo em `docs/catalogo/` |
| `ci` | push/PR | testes |

## Secrets (Settings → Secrets and variables → Actions)
- `KAGGLE_USERNAME`, `KAGGLE_KEY`: obrigatórios para `er-gpu-kaggle` (kaggle.com → Settings → API → Create New Token; verificar telefone).
- `HF_TOKEN`: opcional (modelos com acesso restrito no Hugging Face).

## Regras da máquina
- Nunca adicionar cartão nem usar runners maiores (são sempre pagos). Codespaces só dentro da cota grátis.
- **Nunca commitar binários de terceiros** nem mídia analisada; entradas chegam por URL e saem como artefato temporário.
- Só material próprio, licenciado ou de domínio público; sem DRM.
- Opções descartadas por custo ou fim do plano grátis: larger runners, Gitpod, Firebase Studio, créditos AWS. Oracle Always Free só com cartão (fora da regra por padrão).

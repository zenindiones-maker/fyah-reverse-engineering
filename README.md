# fyah-reverse-engineering

Biblioteca de engenharia reversa e análise de mídia da **Fyah Records**, com foco em **áudio e vídeo** e cobertura de formatos de arquivo, protocolos, binários e modelos de ML.

## Objetivo

Entender *como* faixas e vídeos são construídos (espectro, BPM, tonalidade, timbre, efeitos, mixagem, cortes, ritmo de edição, cores, codecs e formatos) e transformar a análise em perfis JSON reproduzíveis — seguindo o [método da casa](docs/metodologia.md): análise → hipótese → reconstrução → métrica de erro.

## Regras

- **Custo zero sempre, código aberto sempre.** Tudo roda nos runners gratuitos do GitHub Actions (CPU). GPU só em opções gratuitas (Kaggle, Colab grátis, HF Spaces), ver [arsenal](docs/arsenal.md).
- **Só links:** nenhum código de terceiros é copiado para cá; dependências são declaradas no `pyproject.toml` ou instaladas no workflow.
- **Só trabalho legal.** Sem quebrar DRM nem contornar proteções técnicas ou criptografia.
- **Respeitar licenças e termos de uso.** Ferramentas GPL só via CLI isolada; licenças não comerciais (ex.: DeepAFx-ST, Diff-MST) ficam fora do código.
- **Analisar só material próprio, licenciado ou de uso permitido.** Resultados são métricas, nunca redistribuição do conteúdo.

## Estrutura

```
audio/       profile/ (perfil), compare/ (comparador), spectrum, tempo, key, timbre, fx_chain, mix, separation
video/       pacing/ (cortes e ritmo), cuts, color, subtitles, codecs
formats/     formatos de arquivo e protocolos
scripts/     build_catalog.py (gerador do catálogo)
docs/        metodologia, trilha, arsenal, referências, catalogo/
writeups/    relatos de análises
labs/        exercícios práticos
kaggle/      jobs de GPU grátis (Kaggle)
tests/       testes (pytest)
.github/workflows/  ci, catalog-refresh e as 5 ferramentas
```

## Como usar pelo celular (GitHub Actions)

Abra **Actions** no app/site do GitHub → escolha o workflow → **Run workflow** → cole a URL do arquivo. O resultado sai como **artefato** e resumo na página do run.

| Workflow | Entrada | Saída |
|---|---|---|
| `audio-profile` | URL de áudio | `profile.json` (BPM, tonalidade, LUFS, espectro, timbre) |
| `compare` | 2 URLs de áudio | `compare.json` + tabela Markdown |
| `media-inspect` | URL de mídia | `ffprobe.json`, `mediainfo.json` |
| `cuts-pacing` | URL de vídeo | `pacing.json` (cortes, cortes/min, duração dos planos) |
| `stems` | URL de áudio | stems Demucs (CPU) + perfil de cada stem |
| `catalog-refresh` | — (mensal) | atualiza `docs/catalogo/` |
| `er-analyze` | ferramenta + URL(s) | ponto único para todas as ferramentas acima |
| `er-daily` | — (dias úteis 09:00 BRT) | diário de estudo em `docs/diario/` |
| `er-gpu-kaggle` | pasta em `kaggle/` + URL | GPU grátis do Kaggle (precisa de secrets) |

Detalhes da infraestrutura custo zero: [docs/maquina.md](docs/maquina.md).

## Uso local

```bash
pip install -e ".[audio,video,dev]"
python -m audio.profile faixa.wav --out perfil.json
python -m audio.compare a.wav b.wav --md comparacao.md
python -m video.pacing video.mp4 --out pacing.json
pytest -q
```

## Roadmap

- **Fase 0 — Catálogo** ✅: catálogo automático de repositórios open source de RE ([docs/catalogo](docs/catalogo/README.md)), atualizado mensalmente.
- **Fase 1 — Medição** ✅ (v1): perfil de faixa, comparador, inspetor de mídia, cortes e ritmo, stems + perfil por stem.
- **Fase 2 — Inversão de áudio:** estimar EQ/compressão/reverb com DSP diferenciável (dasp-pytorch, grafx) e validar re-renderizando (pedalboard via CLI); dataset ground-truth próprio.
- **Fase 3 — Forense e transcrição:** fingerprint (Chromaprint), marca d'água (AudioSeal), detecção de música IA (SONICS), áudio→MIDI (basic-pitch).
- **Fase 4 — Formatos, binários e protocolos:** parsers Kaitai, rizin/Ghidra headless — só arquivos próprios ou autorizados.
- **Fase 5 — Modelos de ML:** inspeção de arquiteturas e ativações (Netron, nnsight) em GPU gratuita.

## Licença

Apache-2.0. Veja [LICENSE](LICENSE).

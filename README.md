# fyah-reverse-engineering

Biblioteca de engenharia reversa e análise de mídia da **Fyah Records**, com foco em **áudio e vídeo** e cobertura de formatos de arquivo, protocolos, binários e modelos de ML.

## Objetivo

Entender *como* faixas e vídeos são construídos (espectro, BPM, tonalidade, timbre, efeitos, mixagem, cortes, ritmo de edição, cores, codecs e formatos) e transformar a análise em perfis JSON reproduzíveis — seguindo o [método da casa](docs/metodologia.md): análise → hipótese → reconstrução → métrica de erro.

## Regras

- **Custo zero sempre, código aberto sempre.** Tudo roda nos runners gratuitos do GitHub Actions (CPU). Sem GPU externa; ver [arsenal](docs/arsenal.md).
- **Sem API, sem token, sem cadastro.** Nenhuma ferramenta exige chave de API, conta ou cadastro em outro serviço; o único token é o `GITHUB_TOKEN` automático do Actions. Modelos só com pesos públicos baixados anonimamente, rodando em CPU.
  - Lista viva do que passou nesse filtro: [docs/curadoria](docs/curadoria/README.md). O que pede API ou está incerto: [fora.md](docs/curadoria/fora.md).
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
docs/        metodologia, trilha, arsenal, referências, catalogo/, curadoria/
writeups/    relatos de análises
labs/        exercícios práticos
tests/       testes (pytest)
aimem/      orquestrador do AI Memory (harness mestre, zero-LLM)
harness/    DeepSeek Harness + Qwen local (subordinado)
.github/workflows/  ci, catalog-refresh, er-aimemory, er-analyze, er-harness e as ferramentas
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
| `er-aimemory` | ferramenta + URL | **AI Memory (harness mestre)**: smoke zero-LLM + ferramenta sob sessão, memória em `docs/memory/` |
| `er-harness` | tarefa + URL | DeepSeek Harness + llama.cpp local (CPU, sem API nuvem), subordinado ao AI Memory |

Detalhes da infraestrutura custo zero: [docs/maquina.md](docs/maquina.md).

## Harness mestre: AI Memory

O [AI Memory](https://github.com/akitaonrails/ai-memory) (MIT, v3.1.1) manda em tudo. `er-analyze`, `er-harness` (DeepSeek Harness + Qwen local), `er-toolcheck` e `er-aimemory` entram por ele. Cada execução abre uma sessão, recebe o handoff da anterior, registra cada ferramenta e deixa um handoff novo, tudo **sem LLM, sem API e sem cadastro**. A memória durável fica em markdown no git: [docs/memory/](docs/memory/README.md). O binário vem do release oficial, com cache, e nunca é commitado.

## Uso local

```bash
pip install -e ".[audio,video,dev]"
python -m audio.profile faixa.wav --out perfil.json
python -m audio.compare a.wav b.wav --md comparacao.md
python -m video.pacing video.mp4 --out pacing.json
pytest -q
```

## Roadmap

- **Fase 0 — Catálogo** ✅: catálogo automático ([docs/catalogo](docs/catalogo/README.md)) + **curadoria LOCAL_OK** ([docs/curadoria](docs/curadoria/README.md): só ferramentas sem API/token/cadastro; fora listado em `fora.md`).
- **Fase 1 — Medição** ✅ (v1): perfil de faixa, comparador, inspetor de mídia, cortes e ritmo, stems + perfil por stem.
- **Fase 2 — Inversão de áudio:** estimar EQ/compressão/reverb com DSP diferenciável (dasp-pytorch, grafx) e validar re-renderizando (pedalboard via CLI); dataset ground-truth próprio.
- **Fase 3 — Forense e transcrição:** fingerprint (Chromaprint), marca d'água (AudioSeal), detecção de música IA (SONICS), áudio→MIDI (basic-pitch).
- **Fase 4 — Formatos, binários e protocolos:** parsers Kaitai, rizin/Ghidra headless — só arquivos próprios ou autorizados.
- **Fase 5 — Modelos de ML:** inspeção de arquiteturas e ativações (Netron, nnsight) em CPU.

## Licença

Apache-2.0. Veja [LICENSE](LICENSE).

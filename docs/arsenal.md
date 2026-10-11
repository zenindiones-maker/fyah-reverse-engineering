# Arsenal de Engenharia Reversa — Fyah Records (E.R.)

**Premissa:** o usuário opera só pelo celular (Samsung A15). Todo trabalho real roda no **GitHub** (Actions com `workflow_dispatch` disparado pelo app do GitHub ou navegador; Codespaces para editar). Só links: nenhum código de terceiros é copiado para este repo.

**Regra nº 1: custo zero sempre, código aberto sempre.** Nada pago (sem runners pagos, sem APIs pagas). Prioridade: CPU nos runners gratuitos do GitHub Actions.

**Regras legais:** só trabalho legal; sem quebrar DRM; apenas material próprio, licenciado ou de uso permitido; respeitar licenças (atenção às GPL e não-comerciais abaixo).

## Limites do GitHub que guiam tudo
| Item | Runner padrão `ubuntu-latest` (repo público) |
|---|---|
| CPU/RAM | 4 vCPU, 16 GB RAM |
| Disco livre | ~14 GB (dá para liberar +20 GB apagando toolchains pré-instalados) |
| GPU | **não tem** (usar opções gratuitas abaixo) |
| Tempo por job | 6 h; minutos grátis ilimitados em repo público |
| Cache (`actions/cache`) | 10 GB por repo, entradas sem uso expiram em 7 dias |
| Artefatos | `upload-artifact@v4`, retenção configurável (padrão 90 dias), baixáveis no celular |
| Codespaces | cota grátis mensal (~120 h-core, 15 GB); parar ao atingir a cota — nunca ativar cobrança |

Regra prática (custo zero): modelos ≤ ~1 GB em CPU cabem; modelos de geração (ACE-Step) e treino de DSP diferenciável **não** cabem bem → rodar em CPU com trechos curtos ou usar uma GPU **gratuita**:

## GPU gratuita (só quando CPU não der)
| Opção | Limites (aprox., verificar) | Uso |
|---|---|---|
| Kaggle Notebooks | ~30 h GPU/semana (T4 x2 ou P100), sessão até 9–12 h, conta verificada por telefone | treino curto de DSP diferenciável, YourMT3, ACE-Step |
| Google Colab gratuito | T4 sem garantia, sessão ~12 h máx., desconecta por inatividade, cota variável | testes rápidos; funciona no navegador do celular |
| Hugging Face Spaces (CPU básico grátis) / ZeroGPU | CPU 2 vCPU/16 GB grátis; ZeroGPU com cota diária de poucos minutos por usuário e criação de Spaces ZeroGPU restrita a contas PRO | demos/inferência leve; ZeroGPU só usando Spaces públicos existentes |
Nenhuma opção paga é considerada.

## Ferramentas 
Legenda roadmap: **T1** perfil de faixa · **T2** comparador · **T3** inspetor de mídia · **T4** cortes e ritmo · **T5** stems + análise por stem · **F2+** fases futuras (inversão, forense, binários, modelos).

| Repo | Licença | Para que serve | Roadmap | Como roda no GitHub (deps · runner · limites · cache · saída) |
|---|---|---|---|---|
| PySceneDetect | BSD-3 | detecção de cortes por conteúdo/limiar | **T4** | `pip install scenedetect[opencv-headless]` + ffmpeg · ubuntu CPU · ~tempo real p/ 1080p · cache pip · CSV de cenas, thumbs, pacing.json |
| TransNetV2 | MIT | detecção de cortes por ML (transições graduais) | T4 (v2) | TensorFlow CPU; pesos no repo (~30 MB, via git-lfs) · CPU ok · cache `actions/cache` dos pesos · JSON de cortes |
| demucs (htdemucs) | MIT | separação em stems | **T5** | torch CPU + demucs · CPU ~1–3× duração da faixa · cache `~/.cache/torch/hub` · stems MP3/WAV + perfis JSON (retenção 7 dias) |
| python-audio-separator | MIT | separação com BS-RoFormer/MDX/UVR | T5 (qualidade) | `audio-separator[cpu]` · CPU lento (RoFormer ~5–10× duração) · cache da pasta de modelos · stems |
| BS-RoFormer (lucidrains) | MIT | implementação de referência do modelo | estudo T5/F2 | só leitura/estudo; não roda sem pesos |
| beat_this | MIT | beats e downbeats (estado da arte 2024) | **T1** | torch CPU · rápido (s) · cache checkpoint (~80 MB) · beats.json, BPM |
| all-in-one (allin1) | MIT | BPM, beats, seções (intro/refrão) | T1/T2 | exige natten + demucs; CPU lento · cache HF · estrutura.json |
| basic-pitch | Apache-2.0 | transcrição áudio→MIDI | T1 extra/F2 | `pip install basic-pitch` (TF/ONNX leve, modelo embutido) · CPU rápido · MIDI artefato |
| YourMT3 | GPL-3 (verificar; open source) | transcrição multi-instrumento | F2 | modelo ~0.5–1 GB, CPU lento · cache HF · MIDI; isolar por ser GPL |
| pedalboard | GPL-3 | efeitos/plugins, I/O de áudio rápido | T1/T2, dataset ground-truth | `pip install pedalboard` · CPU · gera faixas com FX conhecidos para validar estimadores. GPL: usar como ferramenta, cuidado ao redistribuir junto |
| auraloss | Apache-2.0 | distâncias STFT multi-resolução | **T2** | pip + torch CPU · rápido · métricas no compare.json |
| fadtk | MIT | Fréchet Audio Distance | T2 (conjuntos) | embeddings (CLAP/VGGish/MERT ~0.3–1 GB) · CPU ok p/ poucos minutos de áudio · cache HF |
| dasp-pytorch | Apache-2.0 | EQ/compressor/reverb diferenciáveis | F2 fx_chain (base T2) | torch CPU · otimização por faixa em minutos · parâmetros estimados JSON |
| grafx | Apache-2.0 | grafos de processamento diferenciáveis | F2 fx_chain | torch; GPU recomendado → CPU só com trechos curtos |
| DeepAFx-ST | Adobe Research (não comercial, **não é open source**) | transferência de estilo de FX | ❌ **DESCARTADO** (só leitura de estudo do artigo) | não usar no código; alternativa aberta: dasp-pytorch + grafx |
| Diff-MST | CC BY-NC-SA 4.0 (confirmado; **não é open source**) | inversão de mix multitrack | ❌ **DESCARTADO** (só estudo do método) | não usar no código; reimplementar a ideia com dasp-pytorch (Apache-2.0) |
| ddsp | Apache-2.0 | síntese diferenciável / sound matching | F2 synth_match | TF; treino precisa GPU → Colab/HF sob aprovação |
| DawDreamer | GPL-3 | host de VST/Faust headless em Python | F2 synth_match, dataset | pip wheel Linux · CPU · render de presets |
| audioseal | MIT | marca d'água/detecção em áudio (Meta) | forense F3 | modelo pequeno (~ dezenas de MB) · CPU · relatório JSON |
| sonics | MIT | detecção de música gerada por IA | forense F3 / T2 | modelos SpecTTTra (~100–300 MB) · CPU · score JSON |
| chromaprint | LGPL-2.1/MIT | fingerprint acústico (fpcalc) | T2 (identificação/duplicatas) | `apt install libchromaprint-tools` · CPU instantâneo |
| colour (colour-science) | BSD-3 | ciência de cor, espaços, LUTs | T4 extra (paleta/gradação) | pip · CPU · paleta.json/PNG |
| kaitai_struct + formats | compilador GPL-3, runtime MIT/Apache, specs CC0/variadas | parsers declarativos de formatos | **T3** profundo, formats/ | `kaitai-struct-compiler` (Java) + `pip install kaitaistruct` · CPU · árvore do arquivo JSON |
| ImHex | GPL-2 | editor hex com linguagem de padrões | formats/ (manual) | app desktop; no celular inviável → usar padrões `.hexpat` como documentação |
| PyFLP | GPL-3 | ler projetos FL Studio (.flp) | formats/ DAW | pip · CPU · dump do projeto |
| ghidra | Apache-2.0 | RE de binários (descompilador) | F4 binários | headless (`analyzeHeadless`) em Actions com Java · ~1–2 GB · relatórios. Só binários próprios/com permissão |
| rizin | LGPL-3 | RE de binários CLI | F4 | apt/build · CPU leve · scripts `rz-bin -j` |
| frida | wxWindows (LGPL-like) | instrumentação dinâmica | F4 | precisa alvo rodando; uso só em apps próprios/autorizados; nunca para DRM |
| angr | BSD-2 | execução simbólica | F4 | pip pesado (~1 GB) · CPU · análise pontual |
| netron | MIT | visualizar grafos de modelos (ONNX etc.) | F5 RE de modelos | `pip install netron` gera visualização; no Actions exportar arquitetura |
| nnsight | MIT | inspeção/intervenção em ativações de modelos | F5 (ex.: Demucs, ACE-Step) | torch; modelos pequenos em CPU |
| ACE-Step-1.5 | MIT (código) + pesos MIT (card HF `ACE-Step/Ace-Step1.5`: license:mit, confirmado) | modelo de geração musical (estudo de modelos) | F5 | sem GPU no Actions → Kaggle/Colab gratuito sob aprovação |

## Pesos grandes — NÃO baixados (aguardando aprovação)
Tamanhos aproximados (verificar no card antes de baixar):
| Modelo | Tamanho aprox. | Onde rodaria |
|---|---|---|
| Demucs htdemucs | ~80 MB (htdemucs_ft: ~320 MB, 4 modelos) | Actions CPU + cache |
| BS-RoFormer / Mel-RoFormer (audio-separator) | ~200–650 MB cada | Actions CPU (lento) |
| allin1 (8 modelos ensemble) | ~100–200 MB | Actions CPU |
| beat_this | ~80 MB | Actions CPU |
| YourMT3 | ~0.5–1 GB | Actions CPU (lento) |
| TransNetV2 | ~30 MB | Actions CPU |
| SONICS SpecTTTra | ~100–300 MB | Actions CPU |
| AudioSeal gerador+detector | ~30–60 MB | Actions CPU |
| fadtk embeddings (CLAP/MERT) | ~0.3–1.2 GB | Actions CPU + cache |
| ACE-Step-1.5 | vários GB (~4–8+) | Kaggle/Colab gratuito |

## Workflows propostos (ativos)
Em `.github/workflows/`: `audio-profile.yml`, `compare.yml`, `media-inspect.yml`, `cuts-pacing.yml`, `stems.yml`. Todos `workflow_dispatch` com inputs (URL do arquivo), runner `ubuntu-latest`, timeout definido, cache pip/modelos e resultado em artefato + resumo no `GITHUB_STEP_SUMMARY` (legível no app do GitHub). Pressupõem módulos `audio.profile`, `audio.compare`, `video.pacing` no repo fyah-reverse-engineering (ainda a implementar). Entrada por URL evita commitar mídia; arquivos privados podem vir via Release ou link do Drive.

## Principais achados da pesquisa (2025–2026)
- RE real de áudio = **inverter parâmetros e provar recriando** (análise→hipótese→reconstrução→métrica): DSP diferenciável (dasp, GRAFX, DiffFx, ITO-Master), inversão de mix (Diff-MST, Fx-Encoder++ ISMIR 2025).
- Beats: beat_this (ISMIR 2024) superou madmom; estrutura: allin1.
- Separação: RoFormer (BS/Mel) lidera; Demucs htdemucs segue melhor custo em CPU.
- Forense: AudioSeal (marca d'água), SONICS (detecção de música IA), Chromaprint.
- Vídeo: PySceneDetect + TransNetV2/AutoShot; transições graduais com modelos visão-linguagem (2026).
- Formatos: Kaitai/ImHex em vez de só ffprobe; projetos de DAW (PyFLP).
- Métricas: SI-SDR, STFT multi-resolução (auraloss), FAD (fadtk), erro de LUFS/BPM; dataset ground-truth gerado com pedalboard.
- 

## Status de licença (regra open source)
- ✅ Open source: todos os demais (MIT, Apache-2.0, BSD, GPL/LGPL, wxWindows). GPL é aberto, mas o código que a usa deve ser distribuído sob GPL — manter isolado (scripts/CLI) para o repo seguir Apache-2.0.
- ❌ Descartados/só estudo: DeepAFx-ST (Adobe não comercial), Diff-MST (CC BY-NC-SA).

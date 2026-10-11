# Trilha de aprendizado (custo zero)

## 1. O que um especialista de elite consegue fazer

Elite não é “rodar uma ferramenta”. É o ciclo completo:

1. **Observar** o artefato (binário, áudio, vídeo, firmware, protocolo, modelo, formato).
2. **Hipótese** documentada (o que parece estar acontecendo e por quê).
3. **Testar** a hipótese com ferramenta + experimento reprodutível.
4. **Reconstruir** (parser, stem, receita de FX, dissector, stub, relatório).
5. **Medir o erro** (métrica: SI-SDR, LUFS delta, % de funções recuperadas, etc.).
6. **Provar** no repositório (writeup + artefato + teste automatizado).

Sem reconstrução + métrica, não é engenharia reversa — é só inspeção.

### Áreas cobertas

| Área | O que a elite faz | Exemplos no contexto Fyah |
|---|---|---|
| Binários / malware | triagem estática/dinâmica, unpacking, anti-debug, IOCs, relatório | analisar só binários próprios/autorizados; nunca samples sem sandbox |
| Firmware / hardware | extrair FS, identificar arch, UART/JTAG, emular com QEMU | só dispositivos próprios |
| Protocolos | capturar, inferir campos, máquina de estados, dissector | formatos de rede próprios ou documentados |
| Formatos de arquivo | magic, chunks, Kaitai/.hexpat, round-trip | WAV/RIFF, MP4, Matroska, FLAC, .flp, .als |
| Modelos ML | Netron, safetensors, hooks, ablação, interpretabilidade | Demucs, ACE-Step, WhisperX |
| Áudio / DSP / MIR | perfil → inversão de FX/mix → stems → forense | perfis de referência |
| Vídeo | cortes, ritmo, cor/LUT, legendas, codecs, retenção | perfis de edição |

---

## 2. Matriz de competências

Cada linha: habilidade → como praticar de graça → ferramenta open source → como provar no repo.

### 2.1 Fundamentos (obrigatório para todas as áreas)

| Competência | Praticar de graça | Ferramenta | Provar no repo |
|---|---|---|---|
| Assembly x86-64 / ARM | OST2 Arch 1001; LearnReverseEngineering.com; FLARE Crash Course | Ghidra, rizin, GDB+pwndbg | `writeups/asm/` com desafio resolvido + notas |
| C/C++ → assembly | escrever C simples e descompilar (OST2 RE 2001) | gcc/clang + Ghidra headless | lab com binários gerados no Actions |
| Formatos ELF/PE/Mach-O | pwn.college CSE365 Módulo 5 (cIMG); RE4B (Yurichev) | `readelf`, `objdump`, rizin | parser ou notas em `formats/` |
| Debugging | OST2 Dbg1102 (Ghidra), Dbg1103 (Binja intro); GDB | Ghidra debugger, GDB, x64dbg (Windows) | script de debug + writeup |
| Método científico de RE | FLARE Learning Hub; How2Rev | caderno de hipóteses | template em `docs/metodologia/` + 1 experimento |

### 2.2 Binários e malware (defensivo / autorizado)

| Competência | Praticar de graça | Ferramenta | Provar no repo |
|---|---|---|---|
| Triagem estática | FLARE Malware Crash Course; Epoch Zero REMA | Ghidra, strings, capa, Detect It Easy | relatório JSON + writeup |
| Análise dinâmica (sandbox) | labs FLARE; samples próprios | Frida (apps próprios), strace, Procmon | log + hipóteses confirmadas |
| Packing / unpacking | crackmes.one (nível packing); RevMal | Ghidra + dump de memória | writeup de unpack |
| Anti-debug / anti-VM | How2Rev C03; crackmes | Frida, GDB | notas de bypass **só em labs** |
| YARA / IOCs | escrever regras para labs | yara | `labs/yara/` com regras + testes |
| Go / Rust RE | FLARE Go Reverse Engineering Reference | Ghidra | writeup de 1 binário Go |

**Limite legal:** só samples de labs, CTFs ou material próprio. Sem malware real em máquina sem isolamento. Sem quebrar DRM.

### 2.3 Firmware e hardware

| Competência | Praticar de graça | Ferramenta | Provar no repo |
|---|---|---|---|
| Extração de firmware | imagens públicas de roteadores de lab / CTF | binwalk, firmware-mod-kit | árvore extraída + notas |
| Identificação de arch | OST2 RE 5001 (UEFI) quando disponível | `file`, rizin, Ghidra | relatório de arch |
| Emulação | QEMU user/system com FS extraído | QEMU | script de boot em Actions (quando leve) |
| Interfaces (UART/JTAG) | teoria + fotos de teardowns públicos | documentação | `docs/` com checklist (hardware físico = futuro) |

### 2.4 Protocolos e formatos

| Competência | Praticar de graça | Ferramenta | Provar no repo |
|---|---|---|---|
| Captura e dissecção | Wireshark sample captures; mitmproxy em apps próprios | Wireshark, tshark, mitmproxy | dissector Lua ou notas |
| Inferência de campos | pwn.college cIMG; Netzob (estudo) | Kaitai Struct, ImHex patterns | `.ksy` em `formats/` + teste round-trip |
| Formatos de mídia | specs públicas + ffprobe | kaitai, ffmpeg, MediaInfo | parsers WAV/MP4/MKV |
| Projetos de DAW | arquivos próprios .flp/.als/.rpp | PyFLP, gzip+XML, DawProject | dump JSON em `formats/daw/` |

### 2.5 Modelos de ML

| Competência | Praticar de graça | Ferramenta | Provar no repo |
|---|---|---|---|
| Inspecionar grafo | Netron em ONNX/safetensors públicos | Netron | export PNG/JSON da arquitetura |
| Pesos e shapes | `safetensors`, `torchinfo` | Python | script `models/inspect.py` |
| Hooks / ativações | nnsight em modelos pequenos (CPU) | nnsight | notebook ou Actions com relatório |
| Ablação de parâmetros | grade de experimentos (guidance, steps) | ACE-Step em Kaggle/Colab grátis | tabela de resultados em `eval/` |

### 2.6 Áudio, DSP e MIR (prioridade Fyah)

| Competência | Praticar de graça | Ferramenta | Provar no repo |
|---|---|---|---|
| Perfil de faixa (BPM, key, LUFS, espectro) | FMP Notebooks (Müller); librosa tutorials | librosa, pyloudnorm, beat_this, allin1 | ferramenta T1 + JSON versionado |
| Separação de fontes | demucs docs; mvsep leaderboard (estudo) | Demucs, audio-separator (CPU) | T5 + SI-SDR vs referência |
| Transcrição | basic-pitch docs; YourMT3 (GPL: isolar) | basic-pitch | MIDI + métrica |
| Inversão de FX / mix | Intro to Differentiable DSP (ISMIR 2023); dasp-pytorch | dasp-pytorch, grafx, pedalboard | receita JSON + erro de reconstrução |
| Sound matching / synth | DDSP Magenta notebooks | ddsp, DawDreamer | preset estimado + render |
| Forense de áudio | AudioSeal; Chromaprint; SONICS | audioseal, fpcalc, sonics | relatório forense |
| Dataset ground-truth | gerar com pedalboard cadeias conhecidas | pedalboard | `datasets/` + manifesto |

### 2.7 Vídeo

| Competência | Praticar de graça | Ferramenta | Provar no repo |
|---|---|---|---|
| Codecs / containers / metadados | ffmpeg docs; MediaInfo | ffprobe, pymediainfo | T3 `media-inspect` |
| Detecção de cortes | PySceneDetect; TransNetV2 | scenedetect, TransNetV2 | T4 CSV + pacing.json |
| Ritmo de edição | correlacionar cortes × beats | tools T1+T4 | gráfico + JSON |
| Cor / LUT / paleta | colour-science docs | colour, OpenCV | paleta.json / LUT estimada |
| Legendas / OCR | EasyOCR / PaddleOCR em frames | EasyOCR (CPU) | texto + estilo |
| Forense de vídeo | análise GOP/QP com ffmpeg | ffmpeg `-debug`, ffprobe | relatório de frames |

---

## 3. Certificações pagas vs caminhos equivalentes gratuitos

Certificações oficiais (GREM, OSED, eCRE/eCIR, MRE) **custam dinheiro** → fora da regra. O que importa é a **competência equivalente**, provada no repo.

| Certificação (paga) | O que ela cobre | Caminho gratuito equivalente | Como “certificar” no repo |
|---|---|---|---|
| **GREM** (GIAC Reverse Engineering Malware) | malware Windows, static/dynamic, unpacking | FLARE Learning Hub + Epoch Zero REMA + OST2 RE path + Practical Malware Analysis (livro; labs RPISEC) | 3 writeups de labs + YARA + relatório no estilo GREM |
| **OSED** (OffSec EXP-301) | RE + exploit Windows user-mode, ROP, SEH | Nightmare (guyinatuxedo) + pwn.college + How2Rev + crackmes.one | writeups de 5+ challenges RE/pwn com Ghidra/rizin (só labs) |
| **eCRE / eCIR** (eLearnSecurity) | RE de binários, debugging | OST2 (Arch → RE 2001 → 2102 Ghidra) + LearnReverseEngineering.com | trilha OST2 completa documentada + 10 crackmes |
| **MRE** (Mosse) | RE prático longo | MCSI free curriculum (parte) + crackmes + Flare-On writeups públicos (estudo) | portfólio de writeups |
| *(não existe cert oficial de MIR/DSP)* | áudio/vídeo RE | FMP Notebooks + Intro2DDSP + ISMIR papers + ferramentas do arsenal | as 5 ferramentas T1–T5 + métricas |

**Flare-On** (Mandiant, anual, gratuito): o “PhD prático” de RE. Participar quando abrir; estudar writeups oficiais dos anos anteriores. Crackmes.one RE CTF (2026 já rolou) é o evento irmão focado só em RE.

---

## 5. Trilha de aprendizado em fases (custo zero)

Pensada para rodar **só no celular + GitHub Actions/Codespaces**, sem PC local pesado.

### Fase 0 — Fundação (1–2 semanas)
- Ler este documento + `er_research.md` + `INDEX.md`.
- Completar OST2 Arch 1001 + Dbg1102 (Ghidra).
- Resolver 5 crackmes nível 1–2; 3 desafios picoCTF RE.
- **Entrega no repo:** `docs/trilha/fase-0.md` (checklist) + 1 writeup.

### Fase 1 — Medição áudio/vídeo + método (semanas 1–3 do roadmap Fyah)
- FMP Notebooks caps. relevantes (Fourier, beat, estrutura).
- Implementar T1 (perfil), T3 (inspetor), T4 (cortes) no Actions com `workflow_dispatch`.
- Template de hipótese em `docs/metodologia/`.
- **Prova:** workflows verdes + JSONs de exemplo + teste unitário.

### Fase 2 — RE clássica + formatos (paralelo às semanas 2–6)
- Nightmare (módulos RE) + pwn.college Módulo 5 (cIMG = formato).
- Kaitai: escrever `.ksy` para um formato simples + teste.
- FLARE Crash Course (assembly hacking labs).
- **Prova:** `formats/` com 1 parser; `writeups/` com 3 labs.

### Fase 3 — Inversão áudio + stems (roadmap F2)
- Intro2DDSP + dasp-pytorch em CPU (trechos curtos) ou Kaggle grátis.
- T5 stems (Demucs) + T2 comparador com auraloss.
- Dataset ground-truth com pedalboard.
- **Prova:** receita de FX estimada com erro < limiar documentado.

### Fase 4 — Forense, modelos, binários avançados
- AudioSeal / SONICS / Chromaprint.
- Netron + inspeção ACE-Step (pesos só com aprovação; GPU grátis).
- Ghidra headless no Actions em binário **próprio**.
- Flare-On (quando abrir) ou estudo de writeups oficiais.
- **Prova:** relatório forense + diagrama de modelo + 1 análise headless.

### Fase 5 — Elite (contínuo)
- Publicar writeups próprios (só material permitido).
- Participar de 1 CTF RE por trimestre.
- Rotina diária de autoaprimoramento (abaixo).
- Mentorar o arsenal: propor PRs no plano antes de criar no GitHub.

---

## 8. Rotina diária de autoaprimoramento (proposta)

**Objetivo:** 30–60 min/dia, custo zero, tudo acionável pelo celular.

| Momento | Ação | Onde |
|---|---|---|
| Diário | 1 crackme OU 1 página FMP/OST2 OU 1 hipótese no arsenal | writeup curto ou checkbox na trilha |
| Diário | Rodar 1 workflow (`audio-profile` ou `cuts-pacing`) em arquivo de teste | Actions → artifact no celular |
| Semanal | Atualizar `docs/arsenal/CATALOGO.md` com 1 ferramenta nova (licença + uso) | PR/plano antes de commit |
| Semanal | 1 paper MIR/RE (arXiv) — 5 linhas de nota em `docs/referencias/` | link + resumo próprio |
| Mensal | 1 writeup completo publicado no repo | `writeups/` |
| Trimestral | 1 CTF RE (picoCTF, crackmes CTF, Flare-On se aberto) | writeups + lições |

Automação sugerida (Actions, sem custo):
- Cron semanal (repo público) que abre uma **GitHub Issue** “Drill da semana” com 3 links sorteados da lista de cursos/CTFs (só links, sem baixar nada).
- Ou `workflow_dispatch` “Gerar drill” para o Luiz disparar quando quiser.

---

## 9. Como “dar a si mesmo” essas capacidades (checklist operacional)

Não é mágico: é evidência acumulada no repo.

- [ ] Fase 0 fechada (OST2 + 5 crackmes + 1 writeup).
- [ ] T1, T3, T4 rodando no Actions com artefatos.
- [ ] Template de hipótese usado em ≥ 5 experimentos.
- [ ] 1 parser Kaitai nosso com teste.
- [ ] T2 + T5 com métrica (auraloss / SI-SDR).
- [ ] 1 inspeção de modelo (Netron) documentada.
- [ ] 1 análise Ghidra headless de binário próprio.
- [ ] Equivalência GREM: 3 labs FLARE/RPISEC writeups.
- [ ] Equivalência OSED/RE: Nightmare RE modules + pwn.college M5.
- [ ] Rotina diária ativa por 30 dias seguidos (issues/checkboxes).

Quando a maior parte estiver marcada, o repo **é** a prova de elite — melhor que um PDF de certificação para o contexto Fyah Records.

---


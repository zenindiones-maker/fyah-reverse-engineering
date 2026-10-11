# Status das ferramentas do E.R.

Gerado por `er-toolcheck` em 2026-10-11 15:07 UTC no runner `ubuntu-latest` (CPU). **37/38 OK.** Sem API, sem token, sem cadastro.

| Área | Ferramenta | Status | Detalhe | s |
|---|---|---|---|---|
| audio | librosa | ✅ | librosa 0.11.0, beat_track ok | 26.4 |
| audio | pyloudnorm | ✅ | LUFS -12.3 | 0.0 |
| audio | essentia | ✅ | essentia 2.1-beta6-dev, RhythmExtractor ok | 1.0 |
| audio | pedalboard | ✅ | pedalboard 0.9.26, 88200 amostras processadas | 0.0 |
| audio | audioflux | ✅ | audioflux 0.1.9, mel (128, 83) | 0.6 |
| audio | matchering | ✅ | matchering 2.0.6 (import) | 0.8 |
| audio | music21 | ✅ | music21 10.5.0, key C major | 0.4 |
| audio | PyWavelets | ✅ | pywt 1.8.0 | 0.0 |
| audio | audiomentations | ✅ | audiomentations 0.43.1 | 0.0 |
| audio | mir_eval | ✅ | mir_eval 0.8.2, F=1.0 | 0.0 |
| audio | miditok | ✅ | miditok importado | 1.4 |
| audio | mirdata | ✅ | mirdata 1.0.0, 63 datasets | 0.0 |
| audio | torchaudio (CPU) | ✅ | torch 2.14.1+cpu / torchaudio 2.11.0+cpu (CPU) | 0.0 |
| audio | demucs | ✅ | demucs 4.1.0 (import; pesos públicos baixados só no workflow stems) | 0.0 |
| audio | basic-pitch | ❌ | Unable to convert function return value to a Python type! The signature was 	() -> handle | 0.7 |
| audio | fyah audio.profile | ✅ | fyah audio.profile BPM 117.45 | 0.2 |
| video | ffmpeg | ✅ | ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers | 0.0 |
| video | ffprobe | ✅ | 4.000000 s (ffprobe) | 0.0 |
| video | mediainfo | ✅ | MediaInfoLib - v24.01 | 0.2 |
| video | pymediainfo | ✅ | pymediainfo: 2 trilhas | 0.0 |
| video | PySceneDetect | ✅ | PySceneDetect: 1 corte(s) em 4.0s | 0.2 |
| video | colour-science | ✅ | colour 0.4.7, Lab vermelho [53.2, 80.1, 67.2] | 0.2 |
| video | PyAV | ✅ | PyAV 18.1.0, 40 frames | 0.0 |
| apps | androguard | ✅ | androguard: org.billthefarmer.tuner v1.58, 2 permissões | 0.4 |
| apps | jadx | ✅ | jadx 1.5.6: 22 arquivos .java | 3.4 |
| apps | apktool | ✅ | apktool 2.7.0-dirty: decodificado | 2.3 |
| apps | frida-tools | ✅ | frida-tools 17.23.3 (sem alvo: só versão) | 0.2 |
| formatos | kaitaistruct | ✅ | kaitaistruct runtime 0.11 | 0.0 |
| formatos | construct | ✅ | construct 2.10.70: 5 | 0.0 |
| formatos | hachoir | ✅ | hachoir: Microsoft WAVE audio | 0.1 |
| formatos | python-magic | ✅ | libmagic: Android package (APK), with gradle app-metadata.properties, with APK Signing Block | 0.1 |
| binarios | radare2 | ✅ | radare2 5.5.0 0 @ linux-x86-64 git.5.5.0 | 0.0 |
| binarios | r2pipe | ✅ | r2pipe: x86 64 bits | 0.0 |
| binarios | capstone | ✅ | capstone 5.0.7: push rbp ; mov rbp, rsp ; ret | 0.0 |
| binarios | lief | ✅ | lief 1.0.0-d05b3499b: 31 seções | 0.3 |
| binarios | pefile | ✅ | pefile 2024.8.26 (import) | 0.0 |
| binarios | pyelftools | ✅ | pyelftools: 31 seções | 0.0 |
| binarios | Ghidra headless | ✅ | Ghidra headless: import ok current | 9.6 |

# Status das ferramentas do E.R.

Gerado por `er-toolcheck` em 2026-10-11 15:44 UTC no runner `ubuntu-latest` (CPU). **45/45 OK.** Sem API, sem token, sem cadastro.

| Área | Ferramenta | Status | Detalhe | s |
|---|---|---|---|---|
| audio | librosa | ✅ | librosa 0.11.0, beat_track ok | 27.5 |
| audio | pyloudnorm | ✅ | LUFS -12.3 | 0.0 |
| audio | essentia | ✅ | essentia 2.1-beta6-dev, RhythmExtractor ok | 1.0 |
| audio | pedalboard | ✅ | pedalboard 0.9.26, 88200 amostras processadas | 0.0 |
| audio | audioflux | ✅ | audioflux 0.1.9, mel (128, 83) | 1.7 |
| audio | matchering | ✅ | matchering 2.0.6 (import) | 0.7 |
| audio | music21 | ✅ | music21 10.5.0, key C major | 0.3 |
| audio | PyWavelets | ✅ | pywt 1.8.0 | 0.0 |
| audio | audiomentations | ✅ | audiomentations 0.43.1 | 0.0 |
| audio | mir_eval | ✅ | mir_eval 0.8.2, F=1.0 | 0.2 |
| audio | miditok | ✅ | miditok importado | 1.5 |
| audio | mirdata | ✅ | mirdata 1.0.0, 63 datasets | 0.0 |
| audio | torchaudio (CPU) | ✅ | torch 2.14.1+cpu / torchaudio 2.11.0+cpu (CPU) | 0.0 |
| audio | demucs | ✅ | demucs 4.1.0 (import; pesos públicos baixados só no workflow stems) | 0.0 |
| audio | basic-pitch | ✅ | basic-pitch (ONNX, venv isolada): 16 notas | 19.8 |
| audio | beat_this | ✅ | beat_this: 12 beats, 6 downbeats | 23.2 |
| audio | torchcrepe | ✅ | torchcrepe tiny: f0 mediano 221 Hz (esperado ~220) | 4.9 |
| audio | DawDreamer | ✅ | DawDreamer 0.9.0: render (2, 22050) | 0.0 |
| audio | asteroid | ✅ | asteroid 0.5.2: ConvTasNet forward (1, 2, 8000) (pesos aleatórios) | 6.5 |
| audio | spleeter | ✅ | spleeter 2stems: accompaniment.wav, vocals.wav | 14.2 |
| audio | allin1 | ✅ | allin1: BPM 120, 9 beats, 2 segmentos | 49.6 |
| audio | fyah audio.profile | ✅ | fyah audio.profile BPM 117.45 | 0.2 |
| video | ffmpeg | ✅ | ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers | 0.1 |
| video | ffprobe | ✅ | 4.000000 s (ffprobe) | 0.1 |
| video | mediainfo | ✅ | MediaInfoLib - v24.01 | 0.4 |
| video | pymediainfo | ✅ | pymediainfo: 2 trilhas | 0.0 |
| video | PySceneDetect | ✅ | PySceneDetect: 1 corte(s) em 4.0s | 0.3 |
| video | TransNetV2 | ✅ | TransNetV2 (pytorch): 2 cenas | 8.4 |
| video | colour-science | ✅ | colour 0.4.7, Lab vermelho [53.2, 80.1, 67.2] | 0.2 |
| video | PyAV | ✅ | PyAV 18.1.0, 40 frames | 0.0 |
| apps | androguard | ✅ | androguard: org.billthefarmer.tuner v1.58, 2 permissões | 0.1 |
| apps | jadx | ✅ | jadx 1.5.6: 22 arquivos .java | 3.9 |
| apps | apktool | ✅ | apktool 2.7.0-dirty: decodificado | 2.8 |
| apps | frida-tools | ✅ | frida-tools 17.23.3 (sem alvo: só versão) | 0.2 |
| formatos | kaitaistruct | ✅ | kaitaistruct runtime 0.11 | 0.0 |
| formatos | construct | ✅ | construct 2.10.70: 5 | 0.0 |
| formatos | hachoir | ✅ | hachoir: Microsoft WAVE audio | 0.1 |
| formatos | python-magic | ✅ | libmagic: Android package (APK), with gradle app-metadata.properties, with APK Signing Block | 0.1 |
| binarios | radare2 | ✅ | radare2 5.5.0 0 @ linux-x86-64 git.5.5.0 | 0.1 |
| binarios | r2pipe | ✅ | r2pipe: x86 64 bits | 0.0 |
| binarios | capstone | ✅ | capstone 5.0.7: push rbp ; mov rbp, rsp ; ret | 0.0 |
| binarios | lief | ✅ | lief 1.0.0-d05b3499b: 31 seções | 0.6 |
| binarios | pefile | ✅ | pefile 2024.8.26 (import) | 0.0 |
| binarios | pyelftools | ✅ | pyelftools: 31 seções | 0.0 |
| binarios | Ghidra headless | ✅ | Ghidra headless: import ok current | 13.3 |

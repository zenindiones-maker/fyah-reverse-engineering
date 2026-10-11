# Status das ferramentas do E.R.

Gerado por `er-toolcheck` em 2026-10-11 16:16 UTC no runner `ubuntu-latest` (CPU). **65/71 OK.** Sem API, sem token, sem cadastro.

| Área | Ferramenta | Status | Detalhe | s |
|---|---|---|---|---|
| audio | librosa | ✅ | librosa 0.11.0, beat_track ok | 26.0 |
| audio | pyloudnorm | ✅ | LUFS -12.3 | 0.0 |
| audio | essentia | ✅ | essentia 2.1-beta6-dev, RhythmExtractor ok | 1.0 |
| audio | pedalboard | ✅ | pedalboard 0.9.26, 88200 amostras processadas | 0.0 |
| audio | audioflux | ✅ | audioflux 0.1.9, mel (128, 83) | 0.7 |
| audio | matchering | ✅ | matchering 2.0.6 (import) | 0.6 |
| audio | music21 | ✅ | music21 10.5.0, key C major | 0.3 |
| audio | PyWavelets | ✅ | pywt 1.8.0 | 0.0 |
| audio | audiomentations | ✅ | audiomentations 0.43.1 | 0.1 |
| audio | mir_eval | ✅ | mir_eval 0.8.2, F=1.0 | 0.0 |
| audio | miditok | ✅ | miditok importado | 1.1 |
| audio | mirdata | ✅ | mirdata 1.0.0, 63 datasets | 0.0 |
| audio | torchaudio (CPU) | ✅ | torch 2.14.1+cpu / torchaudio 2.11.0+cpu (CPU) | 1.6 |
| audio | demucs | ✅ | demucs 4.1.0 (import; pesos públicos baixados só no workflow stems) | 0.0 |
| audio | basic-pitch | ✅ | basic-pitch (ONNX, venv isolada): 16 notas | 18.4 |
| audio | beat_this | ✅ | beat_this: 12 beats, 6 downbeats | 5.9 |
| audio | torchcrepe | ✅ | torchcrepe tiny: f0 mediano 221 Hz (esperado ~220) | 4.4 |
| audio | DawDreamer | ✅ | DawDreamer 0.9.0: render (2, 22050) | 0.0 |
| audio | asteroid | ✅ | asteroid 0.5.2: ConvTasNet forward (1, 2, 8000) (pesos aleatórios) | 5.8 |
| audio | spleeter | ✅ | spleeter 2stems: accompaniment.wav, vocals.wav | 12.2 |
| audio | allin1 | ✅ | allin1: BPM 120, 9 beats, 2 segmentos | 47.1 |
| audio | pretty_midi | ✅ | pretty_midi: MIDI 0.5s | 0.0 |
| audio | mido | ❌ | module 'mido' has no attribute '__version__' | 0.0 |
| audio | muspy | ✅ | muspy 0.5.0: 1 trilha(s) | 5.0 |
| audio | partitura | ✅ | partitura: 1 nota(s) | 2.2 |
| audio | resampy | ✅ | resampy: 88200→64000 amostras | 0.8 |
| audio | nnAudio | ❌ | No module named 'nnAudio' | 0.0 |
| audio | chromaprint (fpcalc) | ✅ | chromaprint/fpcalc: fingerprint 20 bytes, 4.0s (local, sem lookup) | 0.0 |
| audio | nussl | ❌ | venv nussl não instalada | 0.0 |
| audio | msaf | ❌ | ImportError: cannot import name 'inf' from 'scipy' (/home/runner/.er-venvs/msaf/lib/python3.10/site-packages/scipy/__init__.py) | 3.9 |
| audio | fyah audio.profile | ✅ | fyah audio.profile BPM 117.45 | 0.2 |
| video | ffmpeg | ✅ | ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers | 0.0 |
| video | ffprobe | ✅ | 4.000000 s (ffprobe) | 0.1 |
| video | mediainfo | ✅ | MediaInfoLib - v24.01 | 0.4 |
| video | pymediainfo | ✅ | pymediainfo: 2 trilhas | 0.0 |
| video | PySceneDetect | ✅ | PySceneDetect: 1 corte(s) em 4.0s | 0.5 |
| video | TransNetV2 | ✅ | TransNetV2 (pytorch): 2 cenas | 7.7 |
| video | colour-science | ✅ | colour 0.4.7, Lab vermelho [53.2, 80.1, 67.2] | 0.3 |
| video | PyAV | ✅ | PyAV 18.1.0, 40 frames | 0.0 |
| video | ffmpy | ✅ | ffmpy importado | 0.0 |
| video | Pillow | ✅ | Pillow 12.3.0: PNG 8x8 | 0.0 |
| apps | androguard | ✅ | androguard: org.billthefarmer.tuner v1.58, 2 permissões | 0.1 |
| apps | jadx | ✅ | jadx 1.5.6: 22 arquivos .java | 2.9 |
| apps | apktool | ✅ | apktool 2.7.0-dirty: decodificado | 2.7 |
| apps | frida-tools | ✅ | frida-tools 17.23.3 (sem alvo: só versão) | 0.3 |
| apps | apkleaks | ✅ | apkleaks: rc=0, saída True | 3.4 |
| apps | objection | ❌ | FileNotFoundError: [Errno 2] No such file or directory: 'objection' | 0.0 |
| formatos | kaitaistruct | ✅ | kaitaistruct runtime 0.11 | 0.0 |
| formatos | construct | ✅ | construct 2.10.70: 5 | 0.0 |
| formatos | hachoir | ✅ | hachoir: Microsoft WAVE audio | 0.2 |
| formatos | python-magic | ✅ | libmagic: Android package (APK), with gradle app-metadata.properties, with APK Signing Block | 0.1 |
| formatos | magika | ✅ | magika: apk | 0.2 |
| formatos | olefile | ✅ | olefile 0.47 (import) | 0.0 |
| formatos | exifread | ✅ | exifread 3.5.1 (import) | 0.0 |
| binarios | radare2 | ✅ | radare2 5.5.0 0 @ linux-x86-64 git.5.5.0 | 0.1 |
| binarios | r2pipe | ✅ | r2pipe: x86 64 bits | 0.0 |
| binarios | capstone | ✅ | capstone 5.0.7: push rbp ; mov rbp, rsp ; ret | 0.0 |
| binarios | lief | ✅ | lief 1.0.0-d05b3499b: 31 seções | 0.5 |
| binarios | pefile | ✅ | pefile 2024.8.26 (import) | 0.0 |
| binarios | pyelftools | ✅ | pyelftools: 31 seções | 0.0 |
| binarios | Ghidra headless | ✅ | Ghidra headless: import ok current | 12.9 |
| binarios | angr | ❌ | AttributeError: module 'bitstring' has no attribute 'ConstBitStream' | 1.2 |
| binarios | unicorn | ✅ | unicorn 2.1.4: x86_64 | 0.1 |
| binarios | keystone | ✅ | keystone: 90 | 0.0 |
| binarios | pyWhat | ✅ | pyWhat PyWhat version 5.1.0 | 0.1 |
| binarios | yara-python | ✅ | yara-python: matches=1 | 0.0 |
| modelos_ml | onnx | ✅ | onnx 1.23.2: modelo vazio ok | 0.1 |
| modelos_ml | onnxruntime | ✅ | onnxruntime 1.31.0: ['AzureExecutionProvider', 'CPUExecutionProvider'] | 0.0 |
| modelos_ml | onnxsim | ✅ | onnxsim v0.8.1 | 0.6 |
| modelos_ml | netron | ✅ | netron 9.3.1 (import; servidor/visualização sob demanda) | 0.0 |
| protocolos | scapy | ✅ | scapy: pacote IP / TCP 127.0.0.1:ftp_data > 127.0.0.1:http S | 0.7 |

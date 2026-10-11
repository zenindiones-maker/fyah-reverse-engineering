# Status das ferramentas do E.R.

Gerado por `er-toolcheck` em 2026-10-11 17:39 UTC no runner `ubuntu-latest` (CPU). **92/92 OK.** Sem API, sem token, sem cadastro.

| Área | Ferramenta | Status | Detalhe | s |
|---|---|---|---|---|
| audio | librosa | ✅ | librosa 0.11.0, beat_track ok | 28.4 |
| audio | pyloudnorm | ✅ | LUFS -12.3 | 0.0 |
| audio | essentia | ✅ | essentia 2.1-beta6-dev, RhythmExtractor ok | 1.0 |
| audio | pedalboard | ✅ | pedalboard 0.9.26, 88200 amostras processadas | 0.0 |
| audio | audioflux | ✅ | audioflux 0.1.9, mel (128, 83) | 0.9 |
| audio | matchering | ✅ | matchering 2.0.6 (import) | 0.6 |
| audio | music21 | ✅ | music21 10.5.0, key C major | 0.3 |
| audio | PyWavelets | ✅ | pywt 1.8.0 | 0.0 |
| audio | audiomentations | ✅ | audiomentations 0.43.1 | 0.0 |
| audio | mir_eval | ✅ | mir_eval 0.8.2, F=1.0 | 0.2 |
| audio | miditok | ✅ | miditok importado | 0.4 |
| audio | mirdata | ✅ | mirdata 1.0.0, 63 datasets | 0.0 |
| audio | torchaudio (CPU) | ✅ | torch 2.14.1+cpu / torchaudio 2.11.0+cpu (CPU) | 3.0 |
| audio | demucs | ✅ | demucs 4.1.0 (import; pesos públicos baixados só no workflow stems) | 0.0 |
| audio | basic-pitch | ✅ | basic-pitch (ONNX, venv isolada): 16 notas | 16.0 |
| audio | beat_this | ✅ | beat_this: 12 beats, 6 downbeats | 5.0 |
| audio | torchcrepe | ✅ | torchcrepe tiny: f0 mediano 221 Hz (esperado ~220) | 4.4 |
| audio | DawDreamer | ✅ | DawDreamer 0.9.0: render (2, 22050) | 0.0 |
| audio | asteroid | ✅ | asteroid 0.5.2: ConvTasNet forward (1, 2, 8000) (pesos aleatórios) | 2.9 |
| audio | spleeter | ✅ | spleeter 2stems: accompaniment.wav, vocals.wav | 7.0 |
| audio | allin1 | ✅ | allin1: BPM 120, 9 beats, 2 segmentos | 38.1 |
| audio | pretty_midi | ✅ | pretty_midi: MIDI 0.5s | 0.0 |
| audio | mido | ✅ | mido: 2 trilha(s) | 0.0 |
| audio | muspy | ✅ | muspy 0.5.0: 1 trilha(s) | 1.8 |
| audio | partitura | ✅ | partitura: 1 nota(s) | 1.8 |
| audio | resampy | ✅ | resampy: 88200→64000 amostras | 0.8 |
| audio | chromaprint (fpcalc) | ✅ | chromaprint/fpcalc: fingerprint 20 bytes, 4.0s (local, sem lookup) | 0.0 |
| audio | msaf | ✅ | msaf 0.1.80: 2 fronteiras | 30.2 |
| audio | python_speech_features | ✅ | python_speech_features: mfcc (398, 13) | 0.0 |
| audio | fast_bss_eval | ✅ | fast_bss_eval: sdr=40.3 dB | 0.0 |
| audio | beets | ✅ | beets 2.14.1 (import CLI disponível) | 0.0 |
| audio | audioseal | ✅ | audioseal detector: saída tuple | 2.2 |
| audio | fyah audio.profile | ✅ | fyah audio.profile BPM 117.45 | 0.2 |
| video | ffmpeg | ✅ | ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers | 0.0 |
| video | ffprobe | ✅ | 4.000000 s (ffprobe) | 0.1 |
| video | mediainfo | ✅ | MediaInfoLib - v24.01 | 0.4 |
| video | pymediainfo | ✅ | pymediainfo: 2 trilhas | 0.0 |
| video | PySceneDetect | ✅ | PySceneDetect: 1 corte(s) em 4.0s | 0.5 |
| video | TransNetV2 | ✅ | TransNetV2 (pytorch): 2 cenas | 3.3 |
| video | colour-science | ✅ | colour 0.4.7, Lab vermelho [53.2, 80.1, 67.2] | 0.3 |
| video | PyAV | ✅ | PyAV 18.1.0, 40 frames | 0.0 |
| video | ffmpy | ✅ | ffmpy importado | 0.0 |
| video | Pillow | ✅ | Pillow 12.3.0: PNG 8x8 | 0.0 |
| video | plotbitrate | ✅ | plotbitrate usage: plotbitrate [-h] [--version] [-s {audio,video}] [-o OUTPUT] | 0.5 |
| video | gopro2gpx | ✅ | gopro2gpx True | 0.0 |
| apps | androguard | ✅ | androguard: org.billthefarmer.tuner v1.58, 2 permissões | 0.1 |
| apps | jadx | ✅ | jadx 1.5.6: 22 arquivos .java | 3.6 |
| apps | apktool | ✅ | apktool 2.7.0-dirty: decodificado | 2.7 |
| apps | frida-tools | ✅ | frida-tools 17.23.3 (sem alvo: só versão) | 0.3 |
| apps | apkleaks | ✅ | apkleaks: rc=0, saída True | 3.4 |
| apps | objection | ✅ | objection 1.12.5 | 0.1 |
| apps | quark-engine | ✅ | quark | 1.1 |
| apps | dex2jar | ✅ | dex2jar d2j-dex2jar -- convert dex to jar | 0.1 |
| apps | smali | ✅ | smali smali 2.5.2.git2771eae-debian (http://smali.org) | 0.1 |
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
| binarios | lief | ✅ | lief 1.0.0-d05b3499b: 31 seções | 0.6 |
| binarios | pefile | ✅ | pefile 2024.8.26 (import) | 0.0 |
| binarios | pyelftools | ✅ | pyelftools: 31 seções | 0.0 |
| binarios | Ghidra headless | ✅ | Ghidra headless: import ok current | 11.1 |
| binarios | angr | ✅ | angr 9.2.213: entry 0x406d30 | 1.3 |
| binarios | unicorn | ✅ | unicorn 2.1.4: x86_64 | 0.1 |
| binarios | keystone | ✅ | keystone: 90 | 0.0 |
| binarios | pyWhat | ✅ | pyWhat PyWhat version 5.1.0 | 0.1 |
| binarios | yara-python | ✅ | yara-python: matches=1 | 0.0 |
| binarios | capa | ✅ | capa capa 9.4.0 | 0.8 |
| binarios | FLOSS | ✅ | floss floss v3.1.1-0-g3cd3ee6 | 0.7 |
| binarios | slither | ✅ | slither 0.11.6 | 0.4 |
| binarios | uncompyle6 | ✅ | uncompyle6 3.9.3 | 0.1 |
| binarios | miasm | ✅ | miasm: Container importado | 0.0 |
| binarios | qiling | ✅ | qiling 1.4.6 | 0.1 |
| binarios | rizin | ✅ | rizin 0.9.1 @ linux-x86-64 | 0.0 |
| modelos_ml | onnx | ✅ | onnx 1.23.2: modelo vazio ok | 0.0 |
| modelos_ml | onnxruntime | ✅ | onnxruntime 1.31.0: ['AzureExecutionProvider', 'CPUExecutionProvider'] | 0.0 |
| modelos_ml | onnxsim | ✅ | onnxsim v0.8.1 | 0.5 |
| modelos_ml | netron | ✅ | netron 9.3.1 (import; servidor/visualização sob demanda) | 0.0 |
| modelos_ml | onnxoptimizer | ✅ | onnxoptimizer: 0 nós | 0.0 |
| protocolos | scapy | ✅ | scapy: pacote IP / TCP 127.0.0.1:ftp_data > 127.0.0.1:http S | 1.0 |
| protocolos | honeypots | ✅ | honeypots importado | 0.3 |
| util | silero-vad | ✅ | silero-vad: 0 segmentos em ruído sintético | 0.8 |
| util | supervision | ✅ | supervision 0.30.9: 1 detecção(ões) | 0.1 |
| util | torch-audiomentations | ✅ | torch-audiomentations: shape (1, 1, 16000) | 0.0 |
| util | fyah tools CLI | ✅ | tools catalog: 12 ferramentas (contrato uniforme) | 0.0 |
| util | harness docs | ✅ | harness: README ok (placeholder LOCAL_LLM_KEY documentado) | 0.0 |

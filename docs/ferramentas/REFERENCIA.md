# Referência (não instaladas)

Triagem automática em `TRIAGEM.csv` (Essencial LOCAL_OK da curadoria).

## Resultado da triagem (2026-10-11)
| Classe | Qtd | Significado |
|---|---|---|
| instalado | ~51–69 | Já no `er-toolcheck` / STATUS |
| instalável (Linux CLI) | ~19 | Pip, apt ou release oficial — lotes 4–6 |
| **referência** | **~359** | Não entram no setup |

## Critérios de “referência”
- Awesome list / coleção de links / learning hub / skill / guide
- Dataset ou paper com código de treino (sem CLI de inferência leve)
- App/GUI desktop (ImHex, Cutter, Recaf, Bytecode Viewer, APKLab, ClassyShark, Hex editors, …)
- Plugin de IDA / Binary Ninja / x64dbg / Ghidra
- Windows-only (x64dbg, PE tools, FLARE-VM, .NET deobfuscators nativos, …)
- iOS / dump de IPA (só com autorização; precisa dispositivo)
- Runtime Frida que exige app alvo vivo (scripts avulsos; `frida-tools`/`objection` já instalados)
- Emuladores/frameworks pesados sem smoke barato restante, ou build difícil (Triton, BAP, …)
- Wrappers de FFmpeg em outras linguagens (já temos ffmpeg/ffprobe/PyAV/ffmpy)
- Ferramentas de patch/bypass (ReVanced, apk-mitm, …) — fora do escopo legal
- Pesquisa áudio/vídeo sem pacote estável (omnizart, Wave-U-Net, AutoShot, …)

## Tentadas e descartadas
- **nussl**: deps antigas (numpy/scipy)
- **nnAudio**: removida do extra (conflito torch no main)
- **crepe** (marl/crepe): build TensorFlow falha no runner; use **torchcrepe** (já OK)
- **paddle2onnx**: exige `paddlepaddle` (GB); fora do orçamento de disco/tempo do Actions
- **apk2url**: pip git instável

Atualize `TRIAGEM.csv` / este arquivo ao promover referência → instalada.

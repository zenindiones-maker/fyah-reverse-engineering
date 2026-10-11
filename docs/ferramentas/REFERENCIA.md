# Referência (não instaladas)

Triagem em `TRIAGEM.csv` (Essencial LOCAL_OK da curadoria).

## Resultado da triagem (atualizado após lotes 4–6)
| Classe | Qtd | Significado |
|---|---|---|
| **instalado** | **67** | No setup-er / er-toolcheck (STATUS: 86 smoke tests) |
| **referência** | **362** | Não entram no setup |
| instalável pendente | **0** | Nada restante que seja CLI Linux estável |

## Critérios de “referência”
- Awesome list / coleção de links / learning hub / skill / guide
- Dataset ou paper com código de treino (sem CLI de inferência leve)
- App/GUI desktop (ImHex, Cutter, Recaf, Bytecode Viewer, APKLab, ClassyShark, Hex editors, …)
- Plugin de IDA / Binary Ninja / x64dbg / Ghidra
- Windows-only (x64dbg, PE tools, FLARE-VM, .NET deobfuscators nativos, …)
- iOS / dump de IPA (só com autorização; precisa dispositivo)
- Runtime Frida que exige app alvo vivo (scripts avulsos; `frida-tools`/`objection` já instalados)
- Emuladores/frameworks pesados ou build difícil (Triton, BAP, …)
- Wrappers de FFmpeg em outras linguagens (já temos ffmpeg/ffprobe/PyAV/ffmpy)
- Ferramentas de patch/bypass (ReVanced, apk-mitm, …) — fora do escopo legal
- Pesquisa áudio/vídeo sem pacote estável (omnizart, Wave-U-Net, AutoShot, …)

## Tentadas e descartadas
- **nussl**: deps antigas (numpy/scipy)
- **nnAudio**: conflito torch no main
- **crepe** (marl/crepe): build TensorFlow falha; use **torchcrepe**
- **paddle2onnx**: exige `paddlepaddle` (GB)
- **apk2url**: pip git instável

Atualize este arquivo ao promover referência → instalada.

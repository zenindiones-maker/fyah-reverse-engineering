# Referência (não instaladas)

Essencial LOCAL_OK da curadoria que **não** entram no `setup-er` / `er-toolcheck` porque são awesome lists, datasets, docs, GUIs, plugins de IDA/x64dbg, Windows-only, frameworks de cheat/bypass, ou repos de pesquisa sem pacote pip/CLI estável. Continuam no [catálogo](../curadoria/) e no [arsenal](../arsenal.md) como estudo.

## Critérios de “referência”
- Awesome list / coleção de links
- Dataset ou paper com código de treino (sem CLI de inferência leve)
- App/GUI desktop (ImHex, Cutter, Recaf, Bytecode Viewer, APKLab, ClassyShark, …)
- Plugin de IDA / Binary Ninja / x64dbg / Ghidra (só usáveis com a ferramenta hospedeira)
- Windows-only (x64dbg, PE tools, FLARE-VM, …)
- Runtime Frida que exige app alvo vivo (scripts, objection já está instalado; dumps de IPA/APK só com autorização)
- Emuladores/frameworks pesados sem smoke test barato (Qiling, Unidbg, Speakeasy, …) — candidatos a lote futuro
- Wrappers de FFmpeg em outras linguagens (já temos ffmpeg/ffprobe/PyAV/ffmpy)
- Ferramentas de patch/bypass (ReVanced, apk-mitm, …) — fora do escopo legal do repo

## Contagem aproximada (429 Essencial LOCAL_OK)
| Área | Essencial | Já instaladas/testadas (STATUS) | Referência / futuros |
|---|---|---|---|
| áudio | 78 | ~30 | datasets (FMA, Jamendo), awesome lists, GUIs (SpleeterGUI), papers sem CLI |
| vídeo | 28 | ~10 | awesome-video, wrappers FFmpeg, AutoShot/OmniShotCut (pesquisa) |
| apps/mobile | 17+ (muitos em binarios) | ~6 | GUIs, scripts Frida, dumpers |
| formatos | 34 | ~6 | hex editors GUI, awesome-kaitai |
| binários | 257 | ~12 | GUIs, plugins, Windows, dumpers, emuladores pesados |
| modelos_ml | 11 | ~4 | VisualDL, demucs.onnx (wrapper) |
| protocolos | 4 | 1 (scapy) | ecapture (precisa eBPF/root), honeypots |

Atualize esta lista ao promover uma ferramenta de referência → instalada.

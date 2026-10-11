# Mapa de integração das ferramentas

Como as ferramentas se alimentam. Só código próprio do repo + libs instaladas em runtime (sem copiar código de terceiros).

```
entrada (URL)
    │
    ├─ áudio ──► audio.profile ──► JSON (BPM, key, LUFS, espectro, timbre)
    │               ├─► beat_this ──► beats/downbeats
    │               ├─► basic-pitch (venv) ──► notas MIDI
    │               ├─► torchcrepe ──► f0
    │               ├─► demucs / spleeter (venv) ──► stems ──► audio.profile ×N
    │               ├─► allin1 (venv) ──► estrutura (segmentos)
    │               └─► audio.compare ◄── 2ª faixa
    │
    │           pipeline audio-full = profile + beat_this + basic-pitch + demucs + perfil por stem
    │
    ├─ vídeo ──► ffprobe / mediainfo / pymediainfo ──► codecs/container
    │               ├─► PySceneDetect / TransNetV2 ──► cortes ──► video.pacing
    │               ├─► colour-science + Pillow/PyAV ──► paleta/cor
    │               └─► faixas de legenda (ffprobe streams)
    │
    │           pipeline video-full = inspect + pacing + cor + legendas
    │
    ├─ APK ──► androguard ──► manifesto/permissões
    │            ├─► jadx ──► Java
    │            ├─► apktool ──► smali/recursos
    │            └─► apkleaks ──► strings/URLs sensíveis (só APKs autorizados)
    │
    │           pipeline apk-full = androguard + jadx + apktool
    │
    ├─ formatos ──► kaitaistruct / construct / hachoir / python-magic / magika
    │
    └─ binários ──► radare2/rizin · capa · FLOSS · capstone · lief · pyelftools · angr · unicorn · keystone · Ghidra headless
                     pipeline binary-inspect = magic + rizin + capa + FLOSS
                     (só arquivos próprios/autorizados; sem DRM)
```

## er-analyze (celular → Run workflow)
| Ferramenta | Entrada | Saída |
|---|---|---|
| audio-profile / compare / stems | áudio | JSON / stems |
| media-inspect / cuts-pacing | mídia | JSON |
| apk-inspect | APK | JSON + MD |
| **audio-full** | áudio | profile + beats + notas + stems + perfil por stem |
| **video-full** | vídeo | ffprobe + pacing + cor + legendas |
| **apk-full** | APK | androguard + jadx + apktool (+ dex2jar/quark se presentes) |
| **binary-inspect** | binário | magic + rizin/radare2 + capa + FLOSS |

## Status
Ver [STATUS.md](STATUS.md) (gerado pelo `er-toolcheck`).

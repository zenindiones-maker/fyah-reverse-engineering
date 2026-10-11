# fyah-reverse-engineering

Biblioteca central de engenharia reversa e análise de mídia da **Fyah Records**, usada pelo **Hazewave** (geração musical) e pelo **BR no GTA** (produção de vídeos).

## Objetivo

Entender *como* faixas e vídeos de referência são construídos (espectro, BPM, tonalidade, timbre, cadeia de efeitos, mixagem, cortes, ritmo de edição, cores, legendas, codecs e formatos) e transformar essa análise em perfis reutilizáveis (JSON) que alimentam o Hazewave e o BR no GTA.

## Regras

- **Só trabalho legal.** Nada de pirataria ou uso indevido de material de terceiros.
- **Sem quebrar DRM** nem contornar qualquer proteção técnica ou criptografia.
- **Respeitar licenças e termos de uso** de softwares, bibliotecas, serviços e conteúdos.
- **Analisar só material próprio, licenciado ou de uso permitido.**
- Os resultados são análises e métricas, nunca redistribuição do conteúdo original.

## Estrutura

```
audio/
  spectrum/    espectrograma, LUFS, faixa dinâmica
  tempo/       BPM e grid de batidas
  key/         tonalidade e acordes
  timbre/      MFCC, perfil de instrumentos
  fx_chain/    estimativa de reverb, compressão, EQ, saturação
  mix/         balanço estéreo, panorama, curva de EQ
  separation/  separação de fontes (Demucs, stems)
  compare/     comparação entre faixas
video/
  cuts/        detecção de cortes
  pacing/      ritmo de edição (cortes por minuto)
  color/       paleta e gradação de cor
  subtitles/   extração e estilo de legendas (OCR/faixas)
  codecs/      codecs, containers e metadados (ffprobe)
formats/       leitura e documentação de formatos de arquivo e protocolos
integrations/
  hazewave/    perfis de referência para geração musical
  br_no_gta/   perfis de edição para os vídeos
docs/          documentação
tests/         testes automatizados
```

## Roadmap: as 5 primeiras ferramentas

1. **Perfil de faixa de áudio**: BPM, tonalidade, loudness e espectro de uma faixa em JSON. É a base de tudo e alimenta o Hazewave diretamente.
2. **Comparador de faixas**: compara uma geração do Hazewave com uma referência de rock psicodélico brasileiro e aponta diferenças de timbre, mix e dinâmica.
3. **Inspetor de mídia**: codecs, container e metadados via `ffprobe`, útil para os renders do BR no GTA no GitHub Actions.
4. **Analisador de cortes e ritmo**: detecta cortes e calcula o ritmo de edição de vídeos de referência para calibrar a edição do BR no GTA.
5. **Separação em stems + análise por stem**: Demucs mais o perfil da ferramenta 1 aplicado em cada stem (bateria, baixo, guitarra, voz).

## Uso (em desenvolvimento)

```bash
pip install -e .
fyah-re --help
```

Requer Python 3.11+.

## Licença

Apache-2.0. Veja [LICENSE](LICENSE).

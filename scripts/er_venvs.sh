#!/usr/bin/env bash
# Venvs isoladas (uv) para ferramentas com dependências conflitantes. Custo zero; pacotes e pesos públicos, sem token.
set -u
V=~/.er-venvs; mkdir -p "$V"
pip install -q uv
mk() { # nome python pacotes...
  n=$1; py=$2; shift 2
  [ -x "$V/$n/bin/python" ] && return 0
  uv venv -q -p "$py" "$V/$n" && VIRTUAL_ENV="$V/$n" uv pip install -q "$@" || { echo "::warning::venv $n falhou"; rm -rf "$V/$n"; }
}
TORCH_CPU="--extra-index-url https://download.pytorch.org/whl/cpu"
mk basicpitch 3.11 "basic-pitch[onnx]" "numpy<2" && VIRTUAL_ENV="$V/basicpitch" uv pip uninstall -q tflite-runtime ai-edge-litert tensorflow tensorflow-cpu coremltools 2>/dev/null || true
mk spleeter 3.10 spleeter
mk asteroid 3.11 $TORCH_CPU torch torchaudio asteroid
mk transnet 3.11 $TORCH_CPU torch transnetv2-pytorch ffmpeg-python
mk allin1 3.11 $TORCH_CPU "torch==2.4.*" torchaudio "natten==0.17.1+torch240cpu" -f https://shi-labs.com/natten/wheels/ allin1 "madmom @ git+https://github.com/CPJKU/madmom"
ls "$V"

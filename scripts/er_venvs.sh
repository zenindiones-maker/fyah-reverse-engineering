#!/usr/bin/env bash
# Venvs isoladas (uv) para ferramentas com dependências conflitantes. Custo zero; pacotes e pesos públicos, sem token.
set -u
V=~/.er-venvs; mkdir -p "$V"
export UV_PYTHON_INSTALL_DIR="$V/.python"  # Pythons do uv dentro do cache (evita symlink quebrado)
pip install -q uv
mk() { # nome python pacotes...
  n=$1; py=$2; shift 2
  [ -x "$V/$n/bin/python" ] && return 0
  uv venv -q --clear -p "$py" "$V/$n" && VIRTUAL_ENV="$V/$n" uv pip install -q "$@" || { echo "::warning::venv $n falhou"; rm -rf "$V/$n"; }
}
TORCH_CPU="--extra-index-url https://download.pytorch.org/whl/cpu"
mk basicpitch 3.11 "basic-pitch[onnx]" "numpy<2" "setuptools<81" && VIRTUAL_ENV="$V/basicpitch" uv pip uninstall -q tflite-runtime ai-edge-litert tensorflow tensorflow-cpu coremltools 2>/dev/null || true
mk spleeter 3.10 spleeter
mk asteroid 3.11 $TORCH_CPU torch torchaudio asteroid requests
mk transnet 3.11 $TORCH_CPU torch transnetv2-pytorch ffmpeg-python
# allin1 precisa de natten<0.18 (sem wheel CPU disponível): compila do PyPI em CPU
if [ ! -x "$V/allin1/bin/python" ]; then
  uv venv -q --clear -p 3.11 "$V/allin1" && export VIRTUAL_ENV="$V/allin1" && \
  uv pip install -q $TORCH_CPU "torch==2.4.*" "torchaudio==2.4.*" setuptools wheel cmake ninja "numpy<2" cython && \
  uv pip install -q --no-build-isolation "natten==0.17.1" && \
  uv pip install -q --no-build-isolation "madmom @ git+https://github.com/CPJKU/madmom" allin1 || { echo "::warning::venv allin1 falhou"; rm -rf "$V/allin1"; }
  unset VIRTUAL_ENV
fi
mk msaf 3.10 msaf "numpy<1.24" "scipy<1.11" "setuptools<81"
mk angr 3.11 $TORCH_CPU "bitstring<4.2" angr unicorn keystone-engine "PyYAML"
mk objection 3.11 objection frida-tools
mk musicxml 3.11 miditok muspy partitura pretty_midi mido
mk audioseal 3.11 $TORCH_CPU torch torchaudio audioseal
mk crepe 3.11 "tensorflow-cpu==2.15.*" crepe "numpy<2" "setuptools<81"
mk qiling 3.11 qiling unicorn
mk gopro 3.11 "gopro2gpx @ git+https://github.com/juanmcasillas/gopro2gpx" || true
mk apk2url 3.11 "apk2url @ git+https://github.com/n0mi1k/apk2url" || true
ls "$V"

#!/usr/bin/env bash
# Sobe llama-server (CPU) com GGUF open-weights baixado anonimamente. Sem API key real.
set -euxo pipefail
ROOT="${ER_TOOLS_DIR:-$HOME/.er-tools}"
MODEL_DIR="$ROOT/models"
BIN_DIR="$ROOT/llama"
mkdir -p "$MODEL_DIR" "$BIN_DIR"
MODEL_URL="${LLAMA_MODEL_URL:-https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf}"
MODEL_FILE="$MODEL_DIR/qwen2.5-0.5b-instruct-q4_k_m.gguf"
if [ ! -f "$MODEL_FILE" ]; then
  echo "Baixando Qwen2.5-0.5B-Instruct Q4_K_M (Apache-2.0, anônimo)…"
  curl -L --fail --retry 3 -A "fyah-re" -o "$MODEL_FILE.partial" "$MODEL_URL"
  mv "$MODEL_FILE.partial" "$MODEL_FILE"
fi
ls -lh "$MODEL_FILE"
if [ ! -x "$BIN_DIR/llama-server" ]; then
  tag=$(gh api repos/ggml-org/llama.cpp/releases --jq '[.[] | select([.assets[].name] | any(test("bin-ubuntu-x64.tar.gz$")))][0].tag_name' 2>/dev/null || true)
  tag=${tag:-b11558}
  echo "llama.cpp release: $tag"
  tmp=$(mktemp -d)
  gh release download "$tag" -R ggml-org/llama.cpp -p "llama-*-bin-ubuntu-x64.tar.gz" -D "$tmp" --clobber
  ls -lh "$tmp"
  tar -xaf "$tmp"/*.tar.gz -C "$BIN_DIR"
  b=$(find "$BIN_DIR" -type f -name llama-server | head -1)
  echo "found: $b"
  [ -n "$b" ]
  ln -sfr "$b" "$BIN_DIR/llama-server"
  chmod +x "$b"
fi
"$BIN_DIR/llama-server" --version || true
exec "$BIN_DIR/llama-server" -m "$MODEL_FILE" --host 127.0.0.1 --port 8080 -c 4096 -t "$(nproc)" --alias qwen2.5-0.5b

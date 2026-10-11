#!/usr/bin/env bash
# Sobe llama-server (CPU) com GGUF Apache-2.0 baixado anonimamente. Sem API key real.
# Uso: MODEL_PRESET=qwen3-4b bash harness/run_local_llm.sh
set -euxo pipefail
ROOT="${ER_TOOLS_DIR:-$HOME/.er-tools}"
MODEL_DIR="$ROOT/models"
BIN_DIR="$ROOT/llama"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRESET="${MODEL_PRESET:-fast}"
mkdir -p "$MODEL_DIR" "$BIN_DIR"

eval "$(python3 - "$SCRIPT_DIR/models.json" "$PRESET" <<'PY'
import json, sys, shlex
regs = json.load(open(sys.argv[1]))
p = sys.argv[2]
if p not in regs:
    sys.stderr.write(f"unknown MODEL_PRESET={p}; choose from {sorted(regs)}\n")
    sys.exit(2)
m = regs[p]
print(f"export MODEL_ID={shlex.quote(m['id'])}")
print(f"export MODEL_NAME={shlex.quote(m['name'])}")
print(f"export MODEL_URL={shlex.quote(m['url'])}")
print(f"export MODEL_CTX={shlex.quote(str(m['ctx']))}")
print(f"export MODEL_FILENAME={shlex.quote(m['file'])}")
PY
)"

GGUF="$MODEL_DIR/$MODEL_FILENAME"
if [ ! -f "$GGUF" ]; then
  echo "Baixando $MODEL_NAME ($PRESET, Apache-2.0, anônimo)…"
  curl -L --fail --retry 3 -A "fyah-re" -o "$GGUF.partial" "$MODEL_URL"
  mv "$GGUF.partial" "$GGUF"
fi
ls -lh "$GGUF"

if [ ! -x "$BIN_DIR/llama-server" ]; then
  tag=$(gh api repos/ggml-org/llama.cpp/releases --jq '[.[] | select([.assets[].name] | any(test("bin-ubuntu-x64.tar.gz$")))][0].tag_name' 2>/dev/null || true)
  tag=${tag:-b11558}
  echo "llama.cpp release: $tag"
  tmp=$(mktemp -d)
  gh release download "$tag" -R ggml-org/llama.cpp -p "llama-*-bin-ubuntu-x64.tar.gz" -D "$tmp" --clobber
  tar -xaf "$tmp"/*.tar.gz -C "$BIN_DIR"
  b=$(find "$BIN_DIR" -type f -name llama-server | head -1)
  echo "found: $b"
  [ -n "$b" ]
  ln -sfr "$b" "$BIN_DIR/llama-server"
  chmod +x "$b"
fi
"$BIN_DIR/llama-server" --version || true
extra=()
case "$PRESET" in
  qwen3-*) extra+=(--jinja) ;;
esac
exec "$BIN_DIR/llama-server" -m "$GGUF" --host 127.0.0.1 --port 8080 \
  -c "$MODEL_CTX" -t "$(nproc)" -np 1 --alias "$MODEL_ID" "${extra[@]}"

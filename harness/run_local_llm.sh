#!/usr/bin/env bash
# Sobe llama-server (CPU) com GGUF open-weights baixado anonimamente. Sem API key real.
set -euxo pipefail
ROOT="${ER_TOOLS_DIR:-$HOME/.er-tools}"
MODEL_DIR="$ROOT/models"
BIN_DIR="$ROOT/llama"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRESET="${MODEL_PRESET:-qwen3-30b-a3b}"
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
print(f"export MODEL_JINJA={shlex.quote('1' if m.get('jinja', True) else '0')}")
print(f"export MODEL_NO_THINK={shlex.quote('1' if m.get('no_think') else '0')}")
print(f"export MODEL_KV_Q8={shlex.quote('1' if m.get('kv_q8') else '0')}")
PY
)"

GGUF="$MODEL_DIR/$MODEL_FILENAME"
if [ ! -f "$GGUF" ]; then
  echo "Baixando $MODEL_NAME ($PRESET, anônimo)…"
  # free disk: drop other cached GGUFs except this target (cache restore may bring several)
  find "$MODEL_DIR" -type f -name '*.gguf' ! -name "$MODEL_FILENAME" -delete 2>/dev/null || true
  curl -L --fail --retry 3 -A "fyah-re" -o "$GGUF.partial" "$MODEL_URL"
  mv "$GGUF.partial" "$GGUF"
fi
ls -lh "$GGUF"
df -h . "$MODEL_DIR" | head -20 || true

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

extra=(-np 1)
if [ "$MODEL_JINJA" = "1" ]; then
  extra+=(--jinja)
fi
if [ "${MODEL_KV_Q8:-0}" = "1" ]; then
  if "$BIN_DIR/llama-server" --help 2>&1 | grep -q -- '--cache-type-k'; then
    extra+=(--cache-type-k q8_0 --cache-type-v q8_0)
  fi
fi
if [ "$MODEL_NO_THINK" = "1" ]; then
  extra+=(--chat-template-kwargs '{"enable_thinking":false}')
fi

exec "$BIN_DIR/llama-server" -m "$GGUF" --host 127.0.0.1 --port 8080 \
  -c "$MODEL_CTX" -t "$(nproc)" --alias "$MODEL_ID" "${extra[@]}"

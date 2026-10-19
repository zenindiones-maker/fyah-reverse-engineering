#!/usr/bin/env bash
# Commita a memória durável (docs/memory/). Falha = exit != 0 + artefato.
# Nunca usa estratégia theirs no pull/rebase.
set -euo pipefail
msg="memoria: ${*:-sessão ai-memory}"
exec python3 -m aimem sync --msg "$msg"

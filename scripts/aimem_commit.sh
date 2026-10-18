#!/usr/bin/env bash
# Commita a memória durável (docs/memory/) gerada pelo AI Memory no run. Só essa pasta.
set -euo pipefail
msg="memoria: ${*:-sessão ai-memory}"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add docs/memory
git diff --cached --quiet && { echo "Memória sem mudanças"; exit 0; }
git commit -q -m "$msg"
for i in 1 2 3 4; do
  git pull --rebase -X theirs -q && git push -q && { echo "memória salva"; exit 0; }
  git rebase --abort 2>/dev/null || true
  sleep $((i * 5))
done
echo "::warning::não consegui salvar docs/memory (conflito); veja o artefato do run"

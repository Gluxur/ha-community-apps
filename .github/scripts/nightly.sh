#!/usr/bin/env bash
# Rescan approved entries one by one. Each result is committed and pushed right
# away (pull --rebase first), and each flagged repository gets its issue right
# away, so a job killed by its time limit or a broken repository loses nothing done.
# Env: GH_TOKEN, GITHUB_TOKEN, FORCE ("--force" or empty).
set -uo pipefail

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

mapfile -t entries < <(python -m tools.catalog approved)
for f in "${entries[@]}"; do
  rm -f /tmp/flagged.json
  # shellcheck disable=SC2086
  if ! python -m tools.catalog nightly --dynamic $FORCE --only "$f" --flagged-out /tmp/flagged.json; then
    echo "::warning::nightly failed for $f"
    git checkout -- "$f" 2>/dev/null || true
    continue
  fi
  if [ -n "$(git status --porcelain -- "$f")" ]; then
    git add -- "$f"
    git commit -q -m "catalog: nightly rescan of $f"
    git pull -q --rebase && git push -q || echo "::warning::could not push $f"
  fi
  if [ -s /tmp/flagged.json ]; then
    python .github/scripts/flagged-issues.py /tmp/flagged.json || echo "::warning::could not open issue for $f"
  fi
done

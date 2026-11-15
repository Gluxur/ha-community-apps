#!/usr/bin/env bash
# Scan every merged submission not yet recorded (entry without `status`) and record
# the review. Processes all pending entries, not only this push's diff, so runs
# cancelled by the concurrency group are caught up by the next one.
# Env: GH_TOKEN, GITHUB_REPOSITORY, GITHUB_ACTOR.
set -euo pipefail

reviewer_for() {
  local sha pr login
  sha=$(git log --diff-filter=A --format=%H -1 -- "$1")
  pr=$(gh api "repos/$GITHUB_REPOSITORY/commits/$sha/pulls" --jq '.[0].number // empty' 2>/dev/null || true)
  login=""
  if [ -n "$pr" ]; then
    login=$(gh api "repos/$GITHUB_REPOSITORY/pulls/$pr" --jq '.merged_by.login // empty' 2>/dev/null || true)
  fi
  echo "${login:-$GITHUB_ACTOR}"
}

mapfile -t pending < <(python -m tools.catalog pending)
for f in "${pending[@]}"; do
  repository=$(python -c 'import sys,yaml; print(yaml.safe_load(open(sys.argv[1]))["repository"])' "$f" \
    | grep -E '^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$')
  reviewer=$(reviewer_for "$f")
  # One broken third-party repository must not block the others.
  if ! python -m tools.catalog scan "$repository" --dynamic --out /tmp/scan.json; then
    echo "::warning::scan failed for $repository; left pending"
    continue
  fi
  python -m tools.catalog apply-review "$f" --reviewer "$reviewer" --scan /tmp/scan.json
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git add "$f"
  git commit -m "catalog: record review of $repository (merged by @$reviewer)"
  # Push after each entry: a long run keeps what it already recorded.
  git pull --rebase -q
  git push
done

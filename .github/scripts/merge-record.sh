#!/usr/bin/env bash
# Scan each newly merged submission (entry without `status`) and record the review.
# Env: GH_TOKEN, BEFORE, GITHUB_SHA, GITHUB_REPOSITORY, GITHUB_ACTOR.
set -euo pipefail

pr=$(gh api "repos/$GITHUB_REPOSITORY/commits/$GITHUB_SHA/pulls" --jq '.[0].number // empty' || true)
reviewer=""
if [ -n "$pr" ]; then
  reviewer=$(gh api "repos/$GITHUB_REPOSITORY/pulls/$pr" --jq '.merged_by.login // empty' || true)
fi
reviewer=${reviewer:-$GITHUB_ACTOR}

mapfile -t changed < <(git diff --name-only "$BEFORE" "$GITHUB_SHA" -- catalog/repositories | grep -E '\.yaml$' || true)
for f in "${changed[@]}"; do
  [ -f "$f" ] || continue
  if python -c 'import sys,yaml; sys.exit(0 if "status" in (yaml.safe_load(open(sys.argv[1])) or {}) else 1)' "$f"; then
    continue
  fi
  repository=$(python -c 'import sys,yaml; print(yaml.safe_load(open(sys.argv[1]))["repository"])' "$f" \
    | grep -E '^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$')
  python -m tools.catalog scan "$repository" --dynamic --out /tmp/scan.json
  python -m tools.catalog apply-review "$f" --reviewer "$reviewer" --scan /tmp/scan.json
done

if [ -n "$(git status --porcelain catalog)" ]; then
  git config user.name "github-actions[bot]"
  git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git add catalog
  git commit -m "catalog: record review (merged by @$reviewer)"
  git push
fi

#!/usr/bin/env bash
# Trusted side of the PR report. Env: GH_TOKEN, HEAD_SHA, GITHUB_REPOSITORY.
# The artifact in ./report is untrusted: its PR number is ignored, and its report
# is only posted when the PR cannot have changed the workflow or the tools.
set -euo pipefail

marker="<!-- community-apps-report -->"

# The open PR whose head is the commit this run was for.
pr=$(gh pr list -R "$GITHUB_REPOSITORY" --state open --search "$HEAD_SHA" --json number,headRefOid \
  --jq ".[] | select(.headRefOid == \"$HEAD_SHA\") | .number" | head -1)
if [ -z "$pr" ]; then
  echo "No open PR with head $HEAD_SHA; nothing to post."
  exit 0
fi

mapfile -t files < <(gh api "repos/$GITHUB_REPOSITORY/pulls/$pr/files" --paginate --jq '.[].filename')
outside=()
for f in "${files[@]}"; do
  case "$f" in
    catalog/repositories/*.yaml) ;;
    *) outside+=("$f") ;;
  esac
done

if [ "${#outside[@]}" -gt 0 ] || [ "${#files[@]}" -ne 1 ]; then
  body="$marker
## Catalog submission

### Blocking

This pull request changes files outside one \`catalog/repositories/<owner>/<repo>.yaml\` entry, so the automatic report cannot be trusted and is not shown. A catalog submission changes exactly one entry file.

Changed files: $(printf '`%s` ' "${files[@]}")"
elif [ -f report/report.md ]; then
  body="$marker
$(head -c 60000 report/report.md)"
else
  body="$marker
## Catalog submission

The scan did not produce a report. See the workflow run for details."
fi

python3 -c 'import json, sys; print(json.dumps({"body": sys.stdin.read()}))' <<< "$body" > body.json

existing=$(gh api "repos/$GITHUB_REPOSITORY/issues/$pr/comments" --paginate \
  --jq ".[] | select(.user.login == \"github-actions[bot]\" and (.body | startswith(\"$marker\"))) | .id" | head -1)
if [ -n "$existing" ]; then
  gh api -X PATCH "repos/$GITHUB_REPOSITORY/issues/comments/$existing" --input body.json > /dev/null
else
  gh api "repos/$GITHUB_REPOSITORY/issues/$pr/comments" --input body.json > /dev/null
fi

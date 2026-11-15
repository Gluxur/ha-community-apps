#!/usr/bin/env bash
# Called from the PR checkout (cwd = pr/), with the trusted tools on PYTHONPATH.
# Env: GH_TOKEN, PR, AUTHOR, GITHUB_REPOSITORY, GITHUB_OUTPUT.
set -u
mkdir -p ../out
echo "$PR" > ../out/pr_number.txt
echo "[]" > ../out/errors.json
# Reviewers come from the trusted CODEOWNERS, never from the PR.
cp ../trusted/CODEOWNERS CODEOWNERS

gh api "repos/$GITHUB_REPOSITORY/pulls/$PR/files" --paginate --jq '.[].filename' > ../out/changed.txt

entry=$(grep -m1 -E '^catalog/repositories/.*\.yaml$' ../out/changed.txt || true)
repository=""
if [ -n "$entry" ] && [ -f "$entry" ]; then
  repository=$(python -P -c 'import sys,yaml; d=yaml.safe_load(open(sys.argv[1])); print(d.get("repository","") if isinstance(d,dict) else "")' "$entry" 2>/dev/null \
    | grep -E '^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$' || true)
fi

# Only works when the token can see the repository's collaborators; otherwise
# "none" and the reviewer confirms maintainership by hand.
permission=none
if [ -n "$repository" ]; then
  permission=$(gh api "repos/$repository/collaborators/$AUTHOR/permission" --jq .permission 2>/dev/null || echo none)
fi
echo "repository=$repository" >> "$GITHUB_OUTPUT"

mapfile -t changed < ../out/changed.txt
if python -P -m tools.catalog validate --author "$AUTHOR" --permission "$permission" \
    --errors-out ../out/errors.json --changed "${changed[@]}"; then
  echo "ok=true" >> "$GITHUB_OUTPUT"
else
  echo "ok=false" >> "$GITHUB_OUTPUT"
fi
exit 0

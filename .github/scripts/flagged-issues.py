"""Open one issue per flagged repository, unless an open one already exists."""

import json
import subprocess
import sys

ASSIGNEE = "Gluxur"

for item in json.load(open(sys.argv[1], encoding="utf-8")):
    title = f"Flagged: {item['repository']}"
    found = subprocess.run(
        ["gh", "issue", "list", "--state", "open", "--search", f'in:title "{title}"', "--json", "title", "--jq", ".[].title"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    if title in found:
        continue
    body = "Signals changed since the last review:\n\n" + "".join(f"- {c}\n" for c in item["changes"])
    body += (
        f"\nEntry: `{item['file']}`\n\n"
        f"Re-approve in a PR with `python -m tools.catalog approve {item['file']} --reviewer <you>`, "
        "or set `status: removed` with a `removed_reason`.\n"
    )
    subprocess.run(["gh", "issue", "create", "--title", title, "--body", body, "--assignee", ASSIGNEE], check=True)

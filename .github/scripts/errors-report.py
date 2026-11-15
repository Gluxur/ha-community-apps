"""Report for a submission that could not be scanned: list the blocking errors."""

import json
import pathlib
import sys

errors = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
text = "## Catalog submission\n\n### Blocking\n\n" + "".join(f"- {e}\n" for e in errors)
pathlib.Path(sys.argv[2]).write_text(text, encoding="utf-8")

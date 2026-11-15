# Community Apps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public, human-reviewed catalog of third-party Home Assistant apps (add-ons), scanned by GitHub Actions, plus a `community_apps` integration whose sidebar panel browses the catalog and adds a repository to the Supervisor in one click.

**Architecture:** Part 1 (Tasks 1–6) is the catalog: one YAML file per app repository, Python tools that validate, scan (static + DNS-logging dynamic run) and build `catalog.json`, and workflows that comment on PRs, record reviews, rescan nightly and publish to GitHub Pages. Part 2 (Tasks 7–11) is the integration: pure logic in `catalog.py` (tested without HA), a coordinator, two admin WebSocket commands, repair issues for flagged/removed installed apps, and a build-free vanilla JS panel. Each part ships and is testable on its own.

**Tech Stack:** Python 3.13, PyYAML, pytest, Docker + dnsmasq (CI only), GitHub Actions + Pages, Home Assistant custom integration (aiohttp, `panel_custom`, repairs), vanilla ES module web component.

**Spec:** `docs/superpowers/specs/2026-11-15-community-apps-design.md`

## Global Constraints

- Repo `Gluxur/ha-community-apps`, domain `community_apps`, title "Community Apps". Never use Home Assistant / Nabu Casa logos or call the project official.
- Human commits: `Gluxur <5436326+Gluxur@users.noreply.github.com>` (set in local git config; global config is a work email, never use it). Automated workflow commits use `github-actions[bot]`.
- UI and README copy never says "safe", "verified", "secure", "sûr", "vérifié", "sans risque". Use "reviewed on entry on <date>" / "relu à l'entrée le <date>" and show signals.
- The integration never installs, updates, uninstalls apps and never removes a store repository. Adding a repository requires an admin action.
- Repository URL given to the Supervisor is exactly `https://github.com/<owner>/<repo>` (same slugs as a manual add).
- Requires a Supervisor (HA OS / Supervised); `homeassistant` minimum `2025.1.0` in `hacs.json`.
- Catalog URL: `https://gluxur.github.io/ha-community-apps/catalog.json`, `schema_version: 1`.
- Statuses: `pending | approved | flagged | removed`; `added_by: author | catalog`.
- Only `approved` repositories can be added from the panel; `high` risk needs explicit confirmation.
- Code, README, catalog in English; integration translations `en` + `fr`.
- PR jobs that touch third-party code run on `pull_request` with read-only token and no secrets; anything needing write access runs in a separate trusted workflow that treats PR output as data.

## Review Focus

1. Catalog fetch fails, returns non-JSON, or has an unknown `schema_version` → integration keeps the last good catalog, panel shows an error banner, existing repair issues are **not** cleared. (Test in Task 8: `test_parse_rejects_unknown_schema`, Task 9 coordinator keeps data.)
2. Supervisor store reports the URL as `https://github.com/Owner/Repo.git/` or `http://…` → still matched to catalog entry `owner/repo`. (Task 8: `test_normalize_repo_url_variants`.)
3. Third-party repo with `config.json`/`config.yml`, apps in nested folders, or one app with invalid YAML → that app reported with an error, others scanned, no crash. (Task 2: `test_scan_invalid_app_does_not_stop_others`.)
4. A PR that edits `tools/`, `.github/` or another entry alongside its catalog file → rejected, so a submitter cannot alter the scanner that judges them. (Task 1: `test_check_pr_paths`.)
5. A submitter writes `status: approved` / `reviewed:` / `scan:` in their own file → rejected. (Task 1: `test_submitted_entry_only_repository`.)

---

## Part 1 — Catalog

### Task 1: Scaffolding and entry validation

**Files:**
- Create: `tools/__init__.py`, `tools/catalog/__init__.py`, `tools/catalog/model.py`
- Create: `pytest.ini`, `requirements_test.txt`, `.gitignore`, `CODEOWNERS`, `catalog/repositories/.gitkeep`
- Test: `tests/tools/test_model.py`

**Interfaces:**
- Produces:
  - `STATUSES = ("pending", "approved", "flagged", "removed")`, `ADDED_BY = ("author", "catalog")`
  - `entry_path(full_name: str) -> str` → `"catalog/repositories/<owner>/<repo>.yaml"` (lowercased)
  - `load_entry(path: Path) -> dict`
  - `validate_entry(entry: dict, path: str, *, submitted: bool) -> list[str]` (error strings, empty = valid)
  - `check_pr_paths(paths: list[str]) -> list[str]`
  - `is_allowed_submitter(full_name: str, author: str, permission: str | None, reviewers: set[str], added_by: str) -> bool`

- [ ] **Step 1: Write failing tests** in `tests/tools/test_model.py`:
  - `test_entry_path`: `entry_path("Hassio-Addons/Repository") == "catalog/repositories/hassio-addons/repository.yaml"`.
  - `test_submitted_entry_only_repository`: `{"repository": "a/b"}` at `entry_path("a/b")` → `[]`; adding any of `status`, `reviewed`, `scan`, `removed_reason` → one error mentioning the key; `added_by: "catalog"` allowed when submitted, `added_by: "author"` allowed, `added_by: "x"` → error.
  - `test_repository_format`: `"a/b c"`, `"a"`, `"https://github.com/a/b"` → error; file path not matching `entry_path(repository)` → error.
  - `test_full_entry_valid`: an entry with `status: approved`, `reviewed: {by, at, commit}`, `scan: {commit, at, apps: []}` validates with `submitted=False`; `status: "ok"` → error; `status: removed` without `removed_reason` → error.
  - `test_check_pr_paths`: `["catalog/repositories/a/b.yaml"]` → `[]`; `["catalog/repositories/a/b.yaml", "tools/catalog/model.py"]` → 1 error; two catalog files → 1 error ("one repository per PR"); `[".github/workflows/x.yml"]` → error.
  - `test_is_allowed_submitter`: owner `a` == author `a` → True (case-insensitive); permission `admin`/`maintain`/`write` → True; `read`/`None` → False; `added_by="catalog"` and author in reviewers → True; `added_by="catalog"` and author not reviewer → False.
- [ ] **Step 2: Run** `python -m pytest tests/tools/test_model.py -v` → FAIL (module missing).
- [ ] **Step 3: Implement `tools/catalog/model.py`.** Repository regex `^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$`. `pytest.ini`: `testpaths = tests`, `pythonpath = .`. `requirements_test.txt`: `pytest==9.2.0`, `pyyaml==6.0.3`, plus the aiohttp pins from `ha-github-private-apps/requirements_test.txt`. `CODEOWNERS`: `/catalog/ @Gluxur` and `* @Gluxur`.
- [ ] **Step 4: Run** tests → PASS.
- [ ] **Step 5: Commit** `feat(catalog): entry model and PR validation rules`.

### Task 2: Static scan

**Files:**
- Create: `tools/catalog/static_scan.py`
- Test: `tests/tools/test_static_scan.py`, fixtures under `tests/tools/fixtures/repo_*/`

**Interfaces:**
- Produces:
  - `scan_repository(root: Path) -> dict` → `{"errors": [str], "apps": [AppScan]}`; errors when no `repository.yaml|yml|json`.
  - `AppScan` (dict): `slug, name, version, arch: list[str], image: "prebuilt"|"source", permissions: list[str], risk, domains: list[str], error: str | None`
  - `permissions(config: dict) -> list[str]` (sorted, unique)
  - `risk(perms: list[str], image: str) -> str`
  - `static_domains(app_dir: Path) -> list[str]`

Permission names (exact):
| config | permission |
|---|---|
| `host_network: true` | `host_network` |
| `privileged` non-empty | `privileged` |
| `full_access: true` | `full_access` |
| `docker_api: true` | `docker_api` |
| `host_pid: true` | `host_pid` |
| `host_dbus: true` | `host_dbus` |
| `apparmor: false` | `apparmor_disabled` |
| `hassio_role: manager` / `admin` | `hassio_role:manager` / `hassio_role:admin` |
| `devices` non-empty | `devices` |
| `uart`/`usb`/`gpio`/`kernel_modules: true` | same name |
| `map` entry writable (`"config:rw"`, `"share:rw"`, `{type: homeassistant_config, read_only: false}` …) | `map_rw:<type>` |

Risk: `high` if any of `full_access, privileged, docker_api, host_pid, hassio_role:manager, hassio_role:admin`; `medium` if any of `host_network, host_dbus, apparmor_disabled, devices, uart, usb, gpio, kernel_modules, map_rw:*` or `image == "prebuilt"`; else `low`. (Spec says "medium: host_network, prebuilt image, hardware access"; `host_dbus`, `apparmor_disabled`, `map_rw` added as medium — Claude's call, recorded in README.)

Domains: regex `https?://([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)` over text files (< 1 MB, decodable UTF-8) in the app dir, skipping `*.md`, `LICENSE*`, `docs/`, `tests/`, `translations/`, `icon.png`/`logo.png`. Plus hosts fetched in `Dockerfile` (`curl`, `wget`, `ADD http…`). Lowercase, sorted, minus the ignore list: `github.com, raw.githubusercontent.com, objects.githubusercontent.com, ghcr.io, docker.io, registry-1.docker.io, home-assistant.io, www.home-assistant.io, developers.home-assistant.io, json-schema.org, www.w3.org, localhost, example.com, example.org, opensource.org, www.apache.org, www.gnu.org`, and any host ending in `.local`.

- [ ] **Step 1: Write fixtures**: `repo_ok/` (`repository.yaml`; `app_a/config.yaml` low risk, build from source, `run.sh` containing `https://api.example-weather.net/v1`; `nested/app_b/config.json` with `full_access: true`, `image: ghcr.io/x/{arch}-b`); `repo_bad/` (`repository.yaml`; `good/config.yml`; `broken/config.yaml` invalid YAML); `repo_none/` (no repository file).
- [ ] **Step 2: Write failing tests:**
  - `test_scan_ok`: 2 apps; `app_a` → `image == "source"`, `risk == "low"`, `domains == ["api.example-weather.net"]`; `app_b` → `permissions == ["full_access"]`, `image == "prebuilt"`, `risk == "high"`.
  - `test_scan_invalid_app_does_not_stop_others`: `repo_bad` → `good` scanned with `error is None`, `broken` present with `error` set, top-level `errors == []`.
  - `test_scan_no_repository_file`: `errors` non-empty.
  - `test_permissions_map_formats`: `{"map": ["config:rw", "share", {"type": "ssl", "read_only": False}]}` → `["map_rw:config", "map_rw:ssl"]`; `{"apparmor": False, "hassio_role": "manager"}` → `["apparmor_disabled", "hassio_role:manager"]`.
  - `test_risk_levels`: `([], "source") == "low"`, `([], "prebuilt") == "medium"`, `(["uart"], "source") == "medium"`, `(["docker_api"], "source") == "high"`.
  - `test_domains_ignore_list`: file with `https://github.com/x`, `http://homeassistant.local:8123`, `https://Example.COM` → `[]`.
- [ ] **Step 3: Run** → FAIL.
- [ ] **Step 4: Implement `static_scan.py`.** App dir = any directory containing `config.yaml|yml|json` (search depth ≤ 3, skip `.git`).
- [ ] **Step 5: Run** → PASS.
- [ ] **Step 6: Commit** `feat(catalog): static scan of app permissions and domains`.

### Task 3: Dynamic scan

**Files:**
- Create: `tools/catalog/dynamic_scan.py`, `tools/catalog/dnsmasq.conf`
- Test: `tests/tools/test_dynamic_scan.py`

**Interfaces:**
- Consumes: `AppScan` from Task 2, the app dir.
- Produces:
  - `parse_dnsmasq_log(text: str) -> list[str]` (queried names, lowercased, sorted, unique, ignore list from Task 2 applied)
  - `image_for(app_dir: Path, config: dict, arch: str = "amd64") -> tuple[str, str] | None` → `("pull", "<image>:<version>")` with `{arch}` substituted, or `("build", "<build_from for arch>")`, or `None` when the arch is unsupported.
  - `run_app(app_dir: Path, config: dict, timeout: int = 180) -> dict` → `{"status": "started"|"failed"|"skipped", "domains": [str]}`

Runner algorithm: create network `cascan-<random>`; start `dnsmasq` container (`4km3/dnsmasq` pinned digest, config `log-queries`, `server=1.1.1.1`) on it; pull or `docker build --build-arg BUILD_FROM=<build_from> <app_dir>`; run the app with `--network cascan-… --dns <dnsmasq ip>`, no volumes, no env, `--memory 512m`; wait `timeout` s; `status = "started"` if the container was still running at least 20 s after start, else `"failed"`; collect `docker logs dnsmasq` → `parse_dnsmasq_log`; always remove containers, image and network. `build_from` comes from `build.yaml|yml|json` (`build_from.amd64`) if present. Limitation (README): only DNS lookups are seen, not direct-IP connections.

- [ ] **Step 1: Write failing tests:** `test_parse_dnsmasq_log` with sample lines `dnsmasq[1]: query[A] API.Weather.net from 172.18.0.3`, `query[AAAA] api.weather.net …`, `query[A] github.com …`, `forwarded api.weather.net to 1.1.1.1` → `["api.weather.net"]`; `test_image_for` with prebuilt `image: ghcr.io/x/{arch}-b` + `version: 1.2` → `("pull", "ghcr.io/x/amd64-b:1.2")`, with `build.yaml` → `("build", "<value>")`, with `arch: [aarch64]` → `None`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Manual check** (Docker host or CI): `python -m tools.catalog scan hassio-addons/repository --dynamic --only <one small app slug>` (CLI from Task 5; run this step after Task 5 if needed) → JSON with `dynamic` set and no leftover `docker ps -a` / `docker network ls` entries named `cascan-*`.
- [ ] **Step 6: Commit** `feat(catalog): dynamic DNS-logging run`.

### Task 4: Signal comparison and PR report

**Files:**
- Create: `tools/catalog/compare.py`, `tools/catalog/report.py`
- Test: `tests/tools/test_compare.py`, `tests/tools/test_report.py`

**Interfaces:**
- Consumes: scan dict from Tasks 2–3 (`apps[*]` with `dynamic` and merged `domains`).
- Produces:
  - `signals(scan: dict) -> dict[str, dict]` → `{slug: {"permissions": [...], "risk": str, "domains": [...]}}`
  - `signal_changes(old: dict, new: dict) -> list[str]` (human lines; empty = unchanged)
  - `render_report(full_name: str, commit: str, scan: dict, errors: list[str]) -> str` (Markdown)

- [ ] **Step 1: Failing tests:**
  - `test_unchanged_when_only_version_differs` → `[]`.
  - `test_new_permission`: old `[]`, new `["docker_api"]` for slug `x` → `["x: new permission docker_api", "x: risk low → high"]` (order: permissions, risk, domains).
  - `test_new_domain` → `["x: new domain t.example.net"]`; removed domain → no line.
  - `test_new_app` → `["new app y (risk medium)"]`; removed app → no line.
  - `test_report_contents`: report contains the repo name, commit short sha (7 chars), a table row per app with risk, every permission, every domain, the dynamic status, validation errors under a "Blocking" heading when present, and the sentence "This report lists signals; it does not prove an app is harmless." Contains none of the forbidden words from Global Constraints.
- [ ] **Step 2–4:** run FAIL → implement → run PASS.
- [ ] **Step 5: Commit** `feat(catalog): signal diff and PR report`.

### Task 5: catalog.json build and CLI

**Files:**
- Create: `tools/catalog/build.py`, `tools/catalog/__main__.py`
- Test: `tests/tools/test_build.py`, `tests/tools/test_cli.py`

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces:
  - `build_catalog(entries: list[dict], now: datetime) -> dict` → `{"schema_version": 1, "generated_at": iso8601Z, "repositories": [...]}`; `approved`/`flagged` entries: `repository, added_by, status, reviewed, scan`; `removed`: only `repository, status, removed_reason`; `pending` excluded; sorted by `repository`.
  - CLI `python -m tools.catalog <cmd>`:
    - `validate --author LOGIN --permission PERM --changed FILE...` → exit 1 with errors on stderr (runs `check_pr_paths`, `validate_entry(submitted=True)`, `is_allowed_submitter`, reviewers read from `CODEOWNERS` `/catalog/` line).
    - `scan OWNER/REPO [--ref SHA] [--dynamic] [--only SLUG] --out FILE` → clones with `git clone --depth 1` (or fetch `--ref`) into a temp dir, writes `{"repository", "commit", "at", "errors", "apps"}`.
    - `report --scan FILE --out FILE` → Markdown.
    - `apply-review FILE --reviewer LOGIN --scan FILE` → sets `status: approved`, `reviewed: {by, at: today, commit}`, `scan`, `added_by` default `author`.
    - `nightly [--dynamic] --flagged-out FILE` → for each `approved` entry whose default-branch head differs from `scan.commit`: rescan; no `signal_changes` → replace `scan`; changes → `status: flagged`, keep old `scan` under `scan`, write new under `pending_scan`, append `{repository, changes}` to the flagged JSON list. Repo 404/archived → appended with change `"repository unavailable"`, status unchanged.
    - `build --out site/catalog.json`.
- [ ] **Step 1: Failing tests:** `test_build_filters_and_shapes` (one entry per status; assert exact keys per status, ordering, `schema_version == 1`); `test_cli_validate_rejects_extra_path` (tmp git-free dir, `--changed catalog/repositories/a/b.yaml tools/x.py` → exit 1); `test_apply_review_sets_fields` (tmp file, fixed scan JSON → YAML has `status: approved`, `reviewed.by == "Gluxur"`, `reviewed.commit == scan.commit`).
- [ ] **Step 2–4:** FAIL → implement (YAML dumped with `sort_keys=False`, key order: `repository, added_by, status, reviewed, removed_reason, scan, pending_scan`) → PASS.
- [ ] **Step 5: Manual check:** `python -m tools.catalog scan hassio-addons/repository --out /tmp/s.json && python -m tools.catalog report --scan /tmp/s.json --out /tmp/r.md` → report lists the repo's apps with plausible permissions; spot-check two against their `config.yaml`.
- [ ] **Step 6: Commit** `feat(catalog): catalog build and CLI`.

### Task 6: Workflows, protections, Pages

**Files:**
- Create: `.github/workflows/catalog-pr.yml`, `catalog-comment.yml`, `catalog-merge.yml`, `catalog-nightly.yml`, `pages.yml`, `validate.yml`
- Create: `.github/PULL_REQUEST_TEMPLATE/add_repository.md`, `.github/ISSUE_TEMPLATE/removal_request.md`

**Interfaces:**
- Consumes: CLI from Task 5.
- Produces: `https://gluxur.github.io/ha-community-apps/catalog.json`.

Workflow contracts:
- `catalog-pr.yml` — `pull_request` on `catalog/**`; `permissions: contents: read`; no secrets. Get changed files (`git diff --name-only origin/main...HEAD`), author permission via `gh api repos/{owner}/{repo}/collaborators/{author}/permission --jq .permission` (unauthenticated-safe; on error pass `none`), run `validate`, `scan --dynamic`, `report`. Upload artifact `report` containing `report.md` and `pr_number.txt`. Fail the job if `validate` fails.
- `catalog-comment.yml` — `workflow_run` of `catalog-pr` (completed); `permissions: pull-requests: write`; downloads artifact, checks `pr_number.txt` matches `^[0-9]+$`, posts/updates one comment marked `<!-- community-apps-report -->` with `report.md` body (truncated to 60 000 chars). Never checks out or runs PR code.
- `catalog-merge.yml` — `push` to `main` on `catalog/repositories/**`; `contents: write`. For each changed entry without `status`: `scan --dynamic`, `apply-review --reviewer <merger>` where merger = `gh api repos/{repo}/commits/{sha}/pulls --jq '.[0].merged_by.login'`; commit as `github-actions[bot]` "catalog: record review of owner/repo"; then trigger `pages.yml` (`gh workflow run`).
- `catalog-nightly.yml` — `schedule: "0 3 * * *"` + `workflow_dispatch`; `contents: write, issues: write`. Run `nightly --dynamic --flagged-out flagged.json`, commit changes, open one issue per flagged repo titled `Flagged: owner/repo` assigned to `Gluxur` with the change lines and a link to the entry (skip if an open issue with that title exists), trigger `pages.yml`.
- `pages.yml` — `push` to `main` on `catalog/**` + `workflow_dispatch`; `pages: write, id-token: write`; `build --out site/catalog.json`, upload with `actions/upload-pages-artifact`, deploy with `actions/deploy-pages`.
- `validate.yml` — copy of `ha-github-private-apps/.github/workflows/validate.yml` (HACS action, hassfest, pytest on 3.13), same pinned SHAs.
- Pin every third-party action by commit SHA.

- [ ] **Step 1: Write the workflows and templates.** The PR template asks the author to confirm they own or maintain the repository and lists what the review looks at.
- [ ] **Step 2: Lint:** `actionlint` (install via `go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.7` or the release binary) → no errors.
- [ ] **Step 3: Repo settings** (`gh api`): enable Pages with source "GitHub Actions"; branch protection on `main`: require PR, 1 approving review, CODEOWNERS review, status check `validate / tests`, no force-push. Allow `github-actions[bot]` pushes for `catalog-merge`/`nightly` (ruleset bypass for the Actions integration).
- [ ] **Step 4: Commit and push** `ci: catalog workflows and Pages`.
- [ ] **Step 5: End-to-end check:** open a test PR from a branch adding `catalog/repositories/hassio-addons/repository.yaml` with `added_by: catalog` → `catalog-pr` passes, report comment appears; merge → entry gets `status: approved`; `pages` deploys; `curl -s https://gluxur.github.io/ha-community-apps/catalog.json | python -m json.tool` shows the entry. Trigger `catalog-nightly` manually → no change, no issue.

---

## Part 2 — Integration

### Task 7: Integration skeleton

**Files:**
- Create: `hacs.json` (`{"name": "Community Apps", "homeassistant": "2025.1.0"}`)
- Create: `custom_components/community_apps/manifest.json`, `const.py`, `config_flow.py`, `supervisor.py`, `__init__.py` (stub setup/unload returning True), `translations/en.json`, `translations/fr.json`, `brand/icon.png` (+ `@2x`, dark variants; neutral store-search glyph, no HA logo)

**Interfaces:**
- Produces:
  - `const.py`: `DOMAIN = "community_apps"`, `CATALOG_URL`, `SCHEMA_VERSION = 1`, `UPDATE_INTERVAL = timedelta(hours=6)`, `PANEL_URL_PATH = "community-apps"`, `PANEL_COMPONENT = "community-apps-panel"`, `STATIC_PATH = "/community_apps_static"`
  - `supervisor.py`: `SupervisorClient(session)` with `repositories()`, `add_repository(url)`, `installed_addons()` copied from `ha-github-private-apps` (same `SupervisorError`, same `_call`), plus `reload_store() -> None` (`POST /store/reload`), `store_addons() -> list[dict]` (`GET /store/addons` → `data["addons"]`), `host_archs() -> list[str]` (`GET /info` → `data["supported_arch"]`)
- Manifest: `domain`, `name: "Community Apps"`, `codeowners: ["@Gluxur"]`, `config_flow: true`, `dependencies: ["hassio", "http", "frontend", "panel_custom", "websocket_api", "repairs"]`, `documentation`/`issue_tracker` → the repo, `integration_type: "service"`, `iot_class: "cloud_polling"`, `requirements: []`, `single_config_entry: true`, `version: "0.1.0"`.
- Config flow: one `user` step, form with no fields; abort `no_supervisor` when `SUPERVISOR`/`SUPERVISOR_TOKEN` env is missing.

- [ ] **Step 1: Write the files.** Translation keys: `config.abort.no_supervisor`, `config.step.user.title/description`, `issues.app_flagged.title/description`, `issues.app_removed.title/description` (placeholders `{app}`, `{repository}`, `{reason}`), all in `en` and `fr`. No `strings.json` (custom integration, as in `github_private_apps`).
- [ ] **Step 2: Verify:** `python -m py_compile custom_components/community_apps/*.py` → no output; `python -c "import json,sys;[json.load(open(f)) for f in sys.argv[1:]]" custom_components/community_apps/manifest.json custom_components/community_apps/translations/*.json hacs.json` → no error.
- [ ] **Step 3: Commit + push**; `validate.yml` HACS and hassfest jobs green.

### Task 8: Pure catalog logic

**Files:**
- Create: `custom_components/community_apps/catalog.py` (no Home Assistant imports, no relative imports — loaded by file path in tests, like `relay.py` in `github_private_apps`)
- Test: `tests/integration/test_catalog.py`

**Interfaces:**
- Produces:
  - `class CatalogError(Exception)`
  - `parse_catalog(data: object, schema_version: int) -> list[dict]` (raises `CatalogError` on non-dict, missing `repositories`, other `schema_version`)
  - `normalize_repo_url(url: str) -> str | None` → `"owner/repo"` lowercased for GitHub URLs (`http(s)`, optional `.git`, trailing `/`), else `None`
  - `repo_url(full_name: str) -> str` → `"https://github.com/<full_name>"` (case preserved)
  - `merge_state(repos: list[dict], store_repos: list[dict], installed: list[dict], store_addons: list[dict], host_archs: list[str]) -> list[dict]` → per repository: catalog fields + `added: bool`, `store_slug: str | None`, and per app: `installed: bool`, `compatible: bool` (app `arch` ∩ `host_archs`), `store_slug: str | None` (from `store_addons` where `repository == store_slug` and slug ends with `_<app slug>`)
  - `issues_for(repos: list[dict], store_repos: list[dict], installed: list[dict]) -> list[dict]` → `{"id": f"{status}_{addon_slug}", "status": "flagged"|"removed", "app": name, "repository": full_name, "reason": str}` for each installed app whose repository is `flagged` (reason: `"signals changed since review"`) or `removed` (`removed_reason`)
  - `can_add(repo: dict, confirm_high_risk: bool) -> str | None` → `None` if allowed, else `"not_approved"` or `"confirmation_required"` (any app `risk == "high"` and not confirmed)

- [ ] **Step 1: Failing tests:** `test_parse_rejects_unknown_schema` (`{"schema_version": 2, …}` → `CatalogError`; `"x"` → `CatalogError`); `test_normalize_repo_url_variants` (`https://github.com/Owner/Repo.git/`, `http://github.com/owner/repo`, `https://github.com/owner/repo` → `"owner/repo"`; `https://gitlab.com/a/b` → `None`); `test_merge_state_marks_added_installed_compatible` (one store repo with `source` `https://github.com/A/B`, slug `abc123`; store addon `abc123_x`; installed `[{"slug": "abc123_x", "repository": "abc123"}]`; host `["amd64"]`; app `arch: ["aarch64"]` → `compatible False`); `test_issues_for_flagged_and_removed` (+ approved yields none, not-installed yields none); `test_can_add` (pending/flagged/removed → `"not_approved"`, high unconfirmed → `"confirmation_required"`, high confirmed → `None`).
- [ ] **Step 2–4:** FAIL → implement → PASS.
- [ ] **Step 5: Commit** `feat(integration): catalog state logic`.

### Task 9: Coordinator, WebSocket API, repairs

**Files:**
- Create: `custom_components/community_apps/coordinator.py`, `websocket.py`, `repairs_sync.py`
- Modify: `custom_components/community_apps/__init__.py`

**Interfaces:**
- Consumes: Task 7 `SupervisorClient`, Task 8 functions.
- Produces:
  - `CommunityAppsCoordinator(DataUpdateCoordinator[dict])`, data `{"repos": list[dict], "catalog_error": str | None, "fetched_at": iso}`. On fetch/parse error with existing data: keep previous `repos`, set `catalog_error`, do **not** raise. With no previous data: raise `UpdateFailed`. Supervisor errors → `UpdateFailed`.
  - WS `community_apps/list` (`@websocket_api.require_admin`) → `{"repositories": merge_state(...), "catalog_error", "fetched_at"}` (fresh Supervisor state per call; catalog from coordinator).
  - WS `community_apps/refresh` (admin) → triggers `coordinator.async_request_refresh()`.
  - WS `community_apps/add_repository` (admin), schema `{repository: str, confirm_high_risk: bool = False}` → error codes `not_in_catalog`, `not_approved`, `confirmation_required`, `supervisor_error`; success → `add_repository(repo_url(...))` unless already added, then `reload_store()`, returns `{"apps": [store slugs of that repo]}`.
  - `sync_issues(hass, issues: list[dict]) -> None`: create via `ir.async_create_issue(hass, DOMAIN, id, is_fixable=False, severity=WARNING|ERROR, translation_key="app_flagged"|"app_removed", translation_placeholders={app, repository, reason}, learn_more_url=f"https://github.com/Gluxur/ha-community-apps/blob/main/{entry_path}")`; delete DOMAIN issues not in the list. Called after each successful coordinator update **only when `catalog_error` is None**.
  - `__init__.py` `async_setup_entry`: build client (raise `ConfigEntryNotReady` on `SupervisorError`), first refresh, register WS commands once (guard in `hass.data`), `hass.http.async_register_static_paths([StaticPathConfig(STATIC_PATH, <dir>/frontend, cache_headers=False)])`, `panel_custom.async_register_panel(hass, frontend_url_path=PANEL_URL_PATH, webcomponent_name=PANEL_COMPONENT, module_url=f"{STATIC_PATH}/panel.js?v=<manifest version>", sidebar_title="Community Apps", sidebar_icon="mdi:store-search-outline", require_admin=True)`. `async_unload_entry`: `frontend.async_remove_panel(hass, PANEL_URL_PATH)`.
- [ ] **Step 1: Implement.** **Step 2: Verify** `python -m py_compile` on all modules; pytest still green.
- [ ] **Step 3: Manual check** on a Supervisor HA (Task 11 install path, or copy the folder to `/config/custom_components/`): add integration → no error in log; Developer tools can't call WS directly, so check via panel in Task 10.
- [ ] **Step 4: Commit** `feat(integration): coordinator, websocket API, repairs`.

### Task 10: Panel

**Files:**
- Create: `custom_components/community_apps/frontend/panel.js` (vanilla `customElements.define(PANEL_COMPONENT, …)`, shadow DOM, no build step, no external imports)
- Test: `tests/integration/test_copy.py`

**Interfaces:**
- Consumes: WS commands from Task 9 via `this.hass.callWS({type: …})`; properties `hass`, `narrow`, `panel` set by HA.

Behavior:
- List view: search box (name, slug, repository, description), filters "Risk" (all/low/medium/high) and "Only compatible with this system" (default on), each repository card shows apps with name, risk chip, compatibility, "added"/"installed" badges, "added by the catalog" when `added_by == "catalog"`, status chip for `flagged`.
- Detail view (click an app): permissions with one plain-English line each (map in the JS, one entry per permission name from Task 2), domains (static + dynamic, with dynamic status), "Reviewed on entry on <date> by <reviewer>", last scan date, links to repository and catalog entry.
- "Add repository" button (approved only; disabled with explanation for flagged/removed). High risk → inline confirmation listing the high-risk permissions before sending `confirm_high_risk: true`. After success → per app, "Open in app store" link `https://my.home-assistant.io/redirect/supervisor_addon/?addon=<store_slug>` (stable across HA versions).
- `catalog_error` → banner "Catalog could not be refreshed; showing data from <fetched_at>" + retry (calls `community_apps/refresh` then `list`).
- Colors only from HA CSS variables (`--primary-text-color`, `--card-background-color`, `--error-color`, `--warning-color`, `--success-color`, `--divider-color`); works at 360 px width; English copy (panel is admin-only; i18n of panel out of v1).
- [ ] **Step 1: Failing test** `test_copy.py::test_no_forbidden_words`: reads `panel.js`, `translations/*.json`, `README.md` (if present) and asserts none contains (case-insensitive, word boundary) `safe`, `verified`, `secure`, `sûr`, `vérifié`, `sans risque`. Run → PASS trivially until files exist, so first add a temporary `panel.js` containing `"verified"` to see it FAIL, then remove.
- [ ] **Step 2: Implement `panel.js`.**
- [ ] **Step 3: Run** `node --check custom_components/community_apps/frontend/panel.js` and pytest → PASS.
- [ ] **Step 4: Manual check** on the Supervisor HA with the catalog from Task 6: panel visible for admin only, search/filters work, detail shows permissions, add a low-risk repo → appears in the native app store, "Open in app store" link opens the app; light and dark theme; phone width.
- [ ] **Step 5: Commit** `feat(integration): sidebar panel`.

### Task 11: README, seeding, release

**Files:**
- Create: `README.md`, `SECURITY.md`, `LICENSE` (MIT, `Gluxur`)
- Create: `catalog/repositories/<owner>/<repo>.yaml` × ~10 (via PRs)

- [ ] **Step 1: README** sections: what it is (community, not official), install (Marketplace badge `https://my.home-assistant.io/redirect/hacs_repository/?owner=Gluxur&repository=ha-community-apps&category=integration`), using the panel, **what the review is and is not** (entry-only review, updates reach users before the nightly rescan, signals not proof, DNS-only dynamic capture, risk rules table from Task 2), publishing your app (PR with one file, owner/maintainer only, what the report checks), removal requests, launch seeding policy (`added_by: catalog`, removal on request without discussion). `test_copy.py` stays green.
- [ ] **Step 2: Seeding:** Gluxur picks ~10 repositories (candidates: `hassio-addons/repository`, `alexbelgium/hassio-addons`, `zigbee2mqtt/hassio-zigbee2mqtt`, `sabeechen/hassio-google-drive-backup` — check each is maintained and not archived). One PR per repo with `added_by: catalog`; Gluxur reads each report and approves. Claude prepares PRs; **Gluxur does the review and merge**.
- [ ] **Step 3: Release:** bump nothing (0.1.0), tag `v0.1.0`, `gh release create v0.1.0 --generate-notes`.
- [ ] **Step 4: End-to-end on Gluxur's HA:** install via the Marketplace custom-repository link, add the integration, open the panel, add one seeded repo, install an app from the native store, then set that repo's entry to `status: flagged` on a branch → after merge and Pages deploy, `community_apps/refresh` → repair issue appears; revert → issue disappears.
- [ ] **Step 5: Commit** `docs: README and launch catalog`.

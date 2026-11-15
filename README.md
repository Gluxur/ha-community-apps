# Community Apps

[![Marketplace](https://img.shields.io/badge/Marketplace-custom%20repository-41BDF5.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Gluxur&repository=ha-community-apps&category=integration)
[![Validate](https://github.com/Gluxur/ha-community-apps/actions/workflows/validate.yml/badge.svg)](https://github.com/Gluxur/ha-community-apps/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A **community catalog of third-party Home Assistant apps** (formerly add-ons), reviewed by a
person when they enter the catalog, plus a sidebar page in Home Assistant to browse it and add
a repository to the app store in one click.

The Home Assistant Marketplace covers integrations, cards, themes and template macros, but not
apps: to install a third-party app you need to know its repository URL. Community Apps fills
that gap.

> **Community project.** Not affiliated with Home Assistant or Nabu Casa.

## Install

Requires Home Assistant OS or Supervised (a Supervisor), Home Assistant 2025.1 or newer.
Home Assistant Container and Core have no app store.

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Gluxur&repository=ha-community-apps&category=integration)

1. Open the repository in the Marketplace (or HACS on older versions) with the button above,
   accept adding it as a custom repository, install **Community Apps**.
2. Settings → Devices & services → Add integration → **Community Apps**.
3. A **Community Apps** entry appears in the sidebar for administrators.

## Using the page

- Search apps, filter by risk, show only apps that run on your system.
- Sort like the Marketplace: GitHub stars (default), recent activity, name, or risk.
- Open an app to read its description and README (loaded from GitHub, written by the app's author) and see **what it can do** (each sensitive permission explained), the **domains
  it contacts**, whether the image is prebuilt or built on your system, and when it was
  reviewed.
- **Add repository to the app store** adds the repository to the Supervisor, exactly as if you
  pasted its URL yourself. Nothing is installed: you then open the app in the native app store
  and install it there. Repositories with high-risk apps ask for confirmation first.
- If an installed app's repository is put back in review or removed from the catalog, a
  **repair** appears in Settings → Repairs.

Community Apps never installs, updates or uninstalls an app and never removes a repository.

## What the review is, and what it is not

- A person reads each repository **when it enters the catalog**, helped by an automatic report.
- **Updates are not reviewed before they reach you.** The Supervisor installs and updates apps
  from the author's repository. Every night, repositories that changed are rescanned; if the
  signals changed (new permission, higher risk, new domain), the entry goes back in review
  (`flagged`), a reviewer is notified, and people who installed the app get a repair. By then
  the update may already be installed.
- The report lists **signals, not proof**. An app can behave differently later, after
  configuration, or only on some systems.
- The dynamic run starts the app for a few minutes in an isolated network, without the
  Supervisor or any configuration, and records **DNS lookups only**: connections to hard-coded
  IP addresses are not seen. Many apps stop early without their configuration; that is
  reported as `failed` and is not a rejection.

### Risk levels

| Risk | When |
|---|---|
| **high** | `full_access`, `privileged`, `docker_api`, `host_pid`, `hassio_role: manager` or `admin` |
| **medium** | `homeassistant_api` (controls your entities), `hassio_api`, `host_network`, `host_dbus`, AppArmor disabled, hardware access (`devices`, `uart`, `usb`, `gpio`, `kernel_modules`), write access to a mapped folder (`/config`, `/share`, `/ssl`…), or a prebuilt image (its source is not checked) |
| **low** | none of the above |

## Publish your app repository

You must be the owner or a maintainer of the repository.

1. Fork this repository and add **one file**, `catalog/repositories/<owner>/<repo>.yaml`
   (lowercase), containing only:

   ```yaml
   repository: owner/repo
   ```

2. Open a pull request that changes only that file. A workflow scans your repository and
   posts a report.
3. A reviewer reads the report and your repository, then merges or asks questions.

After merge, the entry is recorded as reviewed and appears in the catalog within minutes.

## Removal

Open an issue with the *Remove my repository* template. Repositories added by the catalog at
launch (`added_by: catalog`, shown as "added by the catalog") are removed on the author's
request, no questions asked.

## How it works

```
catalog/repositories/<owner>/<repo>.yaml   one file per repository (status, review, last scan)
tools/catalog/                             validation, static + dynamic scan, catalog.json build
.github/workflows/                         PR scan + report, record review on merge,
                                           nightly rescan, publish to GitHub Pages
custom_components/community_apps/          integration: catalog fetch, WebSocket API, repairs,
                                           sidebar panel (frontend/panel.js, no build step)
```

The catalog is published at `https://gluxur.github.io/ha-community-apps/catalog.json`
(`schema_version: 1`).

### Development

```bash
pip install -r requirements_test.txt
pytest                                  # catalog tools + integration logic
python -m tools.catalog scan owner/repo --out scan.json      # add --dynamic with Docker
python -m tools.catalog report --scan scan.json --out report.md
```

Runtime tests against a real Home Assistant core run in CI (`tests/ha`, Linux, Python 3.14):

```bash
pip install pytest-homeassistant-custom-component && pytest tests/ha
```

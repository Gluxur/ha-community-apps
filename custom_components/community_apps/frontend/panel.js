// Community Apps panel. Vanilla web component, no build step.
// Everything coming from the catalog is third-party text: always escaped.

const PERMISSIONS = {
  full_access: "Full access to the host hardware and system.",
  privileged: "Extra Linux capabilities on the host (privileged).",
  docker_api: "Controls Docker on the host: can start any container, which amounts to full host access.",
  host_pid: "Sees every process running on the host.",
  "hassio_role:manager": "Manages the Supervisor: can install, stop and configure other apps.",
  "hassio_role:admin": "Full Supervisor administration, including host and backups.",
  homeassistant_api: "Uses the Home Assistant API: can read and control your entities and devices.",
  hassio_api: "Uses the Supervisor API (information about the system and apps).",
  host_network: "Uses the host network: reaches every device on your network directly.",
  host_dbus: "Talks to the host system bus (D-Bus).",
  apparmor_disabled: "Runs without its AppArmor profile.",
  devices: "Accesses specific hardware devices.",
  uart: "Accesses serial ports.",
  usb: "Accesses USB devices.",
  gpio: "Accesses GPIO pins.",
  kernel_modules: "Can load kernel modules on the host.",
};
const MAP_LABELS = {
  config: "the Home Assistant configuration",
  addon_config: "its own configuration folder",
  all_addon_configs: "the configuration of every app",
  addons: "local app sources",
  share: "/share",
  ssl: "certificates (/ssl)",
  media: "/media",
  backup: "backups",
};
const RISK_ORDER = { high: 0, medium: 1, low: 2 };

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const describePermission = (perm) => {
  if (perm.startsWith("map_rw:")) {
    const kind = perm.slice(7);
    return `Can write to ${MAP_LABELS[kind] || kind}.`;
  }
  return PERMISSIONS[perm] || perm;
};

const fmtDate = (value) => {
  if (!value) return "unknown date";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleDateString();
};

class CommunityAppsPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._error = null;
    this._loading = false;
    this._query = "";
    this._risk = "all";
    this._compatibleOnly = true;
    this._selected = null; // {repository, slug}
    this._confirming = null; // repository awaiting high-risk confirmation
    this._busy = null;
    this._added = {}; // repository -> {apps:[store slugs]} | {error}
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (this._menu) {
      this._menu.hass = hass;
    }
    if (first) this._load();
  }

  set narrow(narrow) {
    this._narrow = narrow;
    if (this._menu) this._menu.narrow = narrow;
  }

  connectedCallback() {
    this._render();
  }

  async _load(refresh = false) {
    if (!this._hass) return;
    this._loading = true;
    this._render();
    try {
      if (refresh) await this._hass.callWS({ type: "community_apps/refresh" });
      this._data = await this._hass.callWS({ type: "community_apps/list" });
      this._error = null;
    } catch (err) {
      this._error = err?.message || String(err);
    }
    this._loading = false;
    this._render();
  }

  async _add(repository, confirmHighRisk) {
    this._busy = repository;
    this._render();
    try {
      const result = await this._hass.callWS({
        type: "community_apps/add_repository",
        repository,
        confirm_high_risk: confirmHighRisk,
      });
      this._added[repository] = { apps: result.apps };
      this._confirming = null;
      this._data = await this._hass.callWS({ type: "community_apps/list" });
    } catch (err) {
      if (err?.code === "confirmation_required") {
        this._confirming = repository;
      } else {
        this._added[repository] = { error: err?.message || String(err) };
      }
    }
    this._busy = null;
    this._render();
  }

  _apps() {
    const repos = this._data?.repositories || [];
    const rows = [];
    for (const repo of repos) {
      if (repo.status === "removed") continue;
      for (const app of repo.scan?.apps || []) {
        if (app.error) continue;
        rows.push({ repo, app });
      }
    }
    const q = this._query.trim().toLowerCase();
    return rows
      .filter(({ repo, app }) => {
        if (this._risk !== "all" && app.risk !== this._risk) return false;
        if (this._compatibleOnly && !app.compatible) return false;
        if (!q) return true;
        return [app.name, app.slug, repo.repository, app.description].some((v) => String(v || "").toLowerCase().includes(q));
      })
      .sort((a, b) => String(a.app.name).localeCompare(String(b.app.name)));
  }

  _riskChip(risk) {
    return `<span class="chip risk-${esc(risk)}">${esc(risk)} risk</span>`;
  }

  _badges(repo, app) {
    const out = [];
    if (repo.status === "flagged") out.push('<span class="chip flagged">back in review</span>');
    if (app.installed) out.push('<span class="chip info">installed</span>');
    else if (repo.added) out.push('<span class="chip info">repository added</span>');
    if (!app.compatible) out.push('<span class="chip muted">not for this system</span>');
    if (repo.added_by === "catalog") out.push('<span class="chip muted">added by the catalog</span>');
    return out.join("");
  }

  _listView() {
    const rows = this._apps();
    const cards = rows
      .map(
        ({ repo, app }) => `
        <button class="card app" data-repo="${esc(repo.repository)}" data-slug="${esc(app.slug)}">
          <div class="row"><span class="name">${esc(app.name)}</span>${this._riskChip(app.risk)}</div>
          <div class="repo">${esc(repo.repository)}${app.version ? ` · ${esc(app.version)}` : ""}</div>
          <div class="badges">${this._badges(repo, app)}</div>
        </button>`
      )
      .join("");
    const total = (this._data?.repositories || []).length;
    return `
      <div class="filters">
        <input id="q" type="search" placeholder="Search apps" value="${esc(this._query)}" aria-label="Search apps">
        <select id="risk" aria-label="Risk">
          ${["all", "low", "medium", "high"].map((r) => `<option value="${r}" ${this._risk === r ? "selected" : ""}>${r === "all" ? "All risks" : `${r} risk`}</option>`).join("")}
        </select>
        <label class="toggle"><input id="compat" type="checkbox" ${this._compatibleOnly ? "checked" : ""}> Only apps for this system</label>
      </div>
      <p class="hint">${rows.length} apps from ${total} repositories. Each repository was reviewed by a person when it entered the catalog; the details list what each app can do.</p>
      <div class="grid">${cards || '<p class="empty">No app matches these filters.</p>'}</div>`;
  }

  _detailView() {
    const repo = (this._data?.repositories || []).find((r) => r.repository === this._selected.repository);
    const app = repo?.scan?.apps?.find((a) => a.slug === this._selected.slug);
    if (!repo || !app) {
      this._selected = null;
      return this._listView();
    }
    const perms = app.permissions?.length
      ? `<ul>${app.permissions.map((p) => `<li><code>${esc(p)}</code> ${esc(describePermission(p))}</li>`).join("")}</ul>`
      : "<p>No sensitive permission requested.</p>";
    const domains = app.domains?.length
      ? `<ul>${app.domains.map((d) => `<li><code>${esc(d)}</code></li>`).join("")}</ul>`
      : "<p>None found.</p>";
    const dynamic = {
      started: "The app was started for a few minutes in an isolated network; the domains above include what it looked up.",
      failed: "The app did not keep running without its configuration, so only domains found in its code are listed.",
      skipped: "The app was not started (architecture not tested), so only domains found in its code are listed.",
    }[app.dynamic || "skipped"];
    const reviewed = repo.reviewed
      ? `Reviewed on entry on ${esc(fmtDate(repo.reviewed.at))} by ${esc(repo.reviewed.by)}. Last scan ${esc(fmtDate(repo.scan?.at))}.`
      : "";
    const entryPath = repo.repository.toLowerCase();
    return `
      <button class="link back" id="back">← All apps</button>
      <div class="card detail">
        <div class="row"><h2>${esc(app.name)}</h2>${this._riskChip(app.risk)}</div>
        <div class="repo">${esc(repo.repository)}${app.version ? ` · version ${esc(app.version)}` : ""} · ${app.image === "prebuilt" ? "prebuilt image" : "built from source on your system"}</div>
        <div class="badges">${this._badges(repo, app)}</div>
        ${repo.status === "flagged" ? '<p class="warn">This repository changed since it was reviewed (new permissions, higher risk or new domains). It is back in review; adding it is paused.</p>' : ""}
        <h3>What it can do</h3>${perms}
        <h3>Domains contacted</h3>${domains}<p class="hint">${esc(dynamic)} Connections to raw IP addresses are not detected.</p>
        <h3>Review</h3>
        <p>${reviewed}</p>
        <p class="hint">The review happens when a repository enters the catalog. Updates reach you before the nightly rescan. The signals above do not prove an app is harmless.</p>
        <p class="links">
          <a href="https://github.com/${esc(repo.repository)}" target="_blank" rel="noopener noreferrer">Repository</a>
          <a href="https://github.com/Gluxur/ha-community-apps/blob/main/catalog/repositories/${esc(entryPath)}.yaml" target="_blank" rel="noopener noreferrer">Catalog entry</a>
        </p>
        ${this._actions(repo, app)}
      </div>`;
  }

  _storeLink(storeSlug, label) {
    return `<a class="button" href="https://my.home-assistant.io/redirect/supervisor_addon/?addon=${encodeURIComponent(storeSlug)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`;
  }

  _actions(repo, app) {
    const added = this._added[repo.repository];
    if (added?.error) return `<p class="warn">Could not add the repository: ${esc(added.error)}</p>`;
    if (repo.added) {
      return app.store_slug ? this._storeLink(app.store_slug, "Open in the app store") : '<p class="hint">Repository added. Reload the app store if the app is not listed yet.</p>';
    }
    if (repo.status !== "approved") return "";
    if (this._busy === repo.repository) return '<button class="button" disabled>Adding…</button>';
    if (this._confirming === repo.repository) {
      const high = new Set();
      for (const a of repo.scan?.apps || []) {
        if (a.risk === "high") for (const p of a.permissions || []) high.add(p);
      }
      return `
        <div class="confirm">
          <p><strong>This repository contains high-risk apps.</strong> Adding it does not install anything, but its apps could request:</p>
          <ul>${[...high].map((p) => `<li><code>${esc(p)}</code> ${esc(describePermission(p))}</li>`).join("")}</ul>
          <button class="button danger" id="confirm-add">Add anyway</button>
          <button class="link" id="cancel-add">Cancel</button>
        </div>`;
    }
    return '<button class="button" id="add">Add repository to the app store</button>';
  }

  _render() {
    if (!this.shadowRoot) return;
    const banner = this._data?.catalog_error
      ? `<div class="banner">The catalog could not be refreshed (${esc(this._data.catalog_error)}); showing data from ${esc(fmtDate(this._data.fetched_at))}. <button class="link" id="retry">Retry</button></div>`
      : "";
    let body;
    if (this._error) body = `<div class="banner">Could not load the catalog: ${esc(this._error)} <button class="link" id="retry">Retry</button></div>`;
    else if (!this._data) body = '<p class="empty">Loading…</p>';
    else body = banner + (this._selected ? this._detailView() : this._listView());

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; min-height: 100vh; background: var(--primary-background-color); color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, sans-serif); }
        header { display: flex; align-items: center; gap: 8px; height: 56px; padding: 0 16px; background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, #fff); }
        header h1 { font-size: 20px; font-weight: 400; margin: 0; flex: 1; }
        main { max-width: 1100px; margin: 0 auto; padding: 16px; box-sizing: border-box; font-size: 14px; line-height: 1.45; }
        .filters { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
        input[type=search], select { padding: 8px 10px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); font-size: 14px; }
        input[type=search] { flex: 1 1 220px; min-width: 0; }
        .toggle { font-size: 14px; display: flex; gap: 6px; align-items: center; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; margin-top: 8px; }
        .card { background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 12px; padding: 12px 14px; text-align: left; color: inherit; font: inherit; }
        button.card { cursor: pointer; width: 100%; }
        button.card:hover { border-color: var(--primary-color); }
        .row { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
        .name { font-weight: 500; overflow-wrap: anywhere; }
        .repo { color: var(--secondary-text-color); font-size: 13px; margin-top: 2px; overflow-wrap: anywhere; }
        .badges { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
        .chip { font-size: 12px; padding: 2px 8px; border-radius: 10px; white-space: nowrap; border: 1px solid var(--divider-color); }
        .risk-low { color: var(--success-color); border-color: var(--success-color); }
        .risk-medium { color: var(--warning-color); border-color: var(--warning-color); }
        .risk-high { color: var(--error-color); border-color: var(--error-color); }
        .flagged { color: var(--warning-color); border-color: var(--warning-color); }
        .info { color: var(--primary-color); border-color: var(--primary-color); }
        .muted { color: var(--secondary-text-color); }
        .hint { color: var(--secondary-text-color); font-size: 13px; }
        .empty { color: var(--secondary-text-color); }
        .banner, .warn { border-left: 4px solid var(--warning-color); padding: 8px 12px; background: var(--card-background-color); margin: 0 0 12px; }
        .detail h2 { margin: 0; font-size: 22px; font-weight: 400; overflow-wrap: anywhere; }
        .detail h3 { font-size: 15px; margin: 18px 0 6px; }
        .detail ul { padding-left: 20px; margin: 4px 0; }
        .detail li { margin: 4px 0; overflow-wrap: anywhere; }
        code { font-size: 12px; background: var(--secondary-background-color, rgba(127,127,127,.15)); padding: 1px 4px; border-radius: 4px; }
        .links { display: flex; gap: 16px; }
        a { color: var(--primary-color); }
        .button { display: inline-block; margin-top: 12px; padding: 10px 16px; border-radius: 8px; border: none; background: var(--primary-color); color: var(--text-primary-color, #fff); font: inherit; cursor: pointer; text-decoration: none; }
        .button[disabled] { opacity: .6; cursor: default; }
        .button.danger { background: var(--error-color); }
        .link { background: none; border: none; color: var(--primary-color); font: inherit; cursor: pointer; padding: 4px 0; }
        .back { margin-bottom: 8px; }
        .confirm { margin-top: 12px; border: 1px solid var(--error-color); border-radius: 8px; padding: 8px 12px; }
        .refresh { background: none; border: none; color: inherit; font-size: 14px; cursor: pointer; }
      </style>
      <header><span id="menu"></span><h1>Community Apps</h1><button class="refresh" id="refresh" ${this._loading ? "disabled" : ""}>${this._loading ? "Refreshing…" : "Refresh"}</button></header>
      <main>${body}</main>`;
    this._wire();
  }

  _wire() {
    const root = this.shadowRoot;
    const slot = root.getElementById("menu");
    if (slot && customElements.get("ha-menu-button")) {
      this._menu = this._menu || document.createElement("ha-menu-button");
      this._menu.hass = this._hass;
      this._menu.narrow = this._narrow;
      slot.appendChild(this._menu);
    }
    root.getElementById("refresh")?.addEventListener("click", () => this._load(true));
    root.getElementById("retry")?.addEventListener("click", () => this._load(true));
    const q = root.getElementById("q");
    if (q) {
      q.addEventListener("input", (e) => {
        this._query = e.target.value;
        const pos = e.target.selectionStart;
        this._render();
        const again = this.shadowRoot.getElementById("q");
        again.focus();
        again.setSelectionRange(pos, pos);
      });
    }
    root.getElementById("risk")?.addEventListener("change", (e) => {
      this._risk = e.target.value;
      this._render();
    });
    root.getElementById("compat")?.addEventListener("change", (e) => {
      this._compatibleOnly = e.target.checked;
      this._render();
    });
    root.querySelectorAll("button.app").forEach((el) =>
      el.addEventListener("click", () => {
        this._selected = { repository: el.dataset.repo, slug: el.dataset.slug };
        this._render();
        window.scrollTo(0, 0);
      })
    );
    root.getElementById("back")?.addEventListener("click", () => {
      this._selected = null;
      this._confirming = null;
      this._render();
    });
    const current = this._selected?.repository;
    root.getElementById("add")?.addEventListener("click", () => this._add(current, false));
    root.getElementById("confirm-add")?.addEventListener("click", () => this._add(current, true));
    root.getElementById("cancel-add")?.addEventListener("click", () => {
      this._confirming = null;
      this._render();
    });
  }
}

customElements.define("community-apps-panel", CommunityAppsPanel);

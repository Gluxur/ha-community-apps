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
const SORTS = {
  name: "App name",
  stars: "Stars",
  updated: "Activity",
  risk: "Risk",
  status: "Status",
  repository: "Repository",
};

const byName = (a, b) => String(a.app.name).localeCompare(String(b.app.name), undefined, { sensitivity: "base" });
const time = (value) => {
  const t = Date.parse(value || "");
  return Number.isNaN(t) ? -Infinity : t;
};

// Raw GitHub base URL of an app folder at `ref`, or null when the path is unusable.
function rawBase(repo, app, ref) {
  const path = app?.path;
  if (typeof path !== "string" || path.split("/").includes("..") || !ref) return null;
  const dir = path === "." || path === "" ? "" : `${path.split("/").map(encodeURIComponent).join("/")}/`;
  return `https://raw.githubusercontent.com/${repo.repository}/${encodeURIComponent(ref)}/${dir}`;
}

// README.md, then DOCS.md (what the app store shows), from the current repository.
export function readmeUrls(repo, app) {
  const base = rawBase(repo, app, "HEAD");
  return base ? [`${base}README.md`, `${base}DOCS.md`] : [];
}

// Icon from the reviewed commit, so it cannot change after the review.
export function iconUrl(repo, app) {
  const base = rawBase(repo, app, repo.scan?.commit);
  return base ? `${base}icon.png` : null;
}

export const riskOf = (app) => (app?.risk in RISK_ORDER ? app.risk : "low");

export const defaultFilters = () => ({ status: [], risk: [], source: [], compatible: true });

// Row status, in the order the Marketplace groups them (most urgent first).
const STATUS_ORDER = ["flagged", "installed", "added", "new", "available"];
const STATUS_LABELS = {
  flagged: "Back in review",
  installed: "Installed",
  added: "Repository added",
  new: "New",
  available: "Available",
};
const RISK_LABELS = { high: "High risk", medium: "Medium risk", low: "Low risk" };
const NEW_DAYS = 14;

export function rowStatus(repo, app, now = Date.now()) {
  if (repo.status === "flagged") return "flagged";
  if (app.installed) return "installed";
  if (repo.added) return "added";
  const reviewedAt = Date.parse(repo.reviewed?.at || "");
  if (!Number.isNaN(reviewedAt) && now - reviewedAt < NEW_DAYS * 86400000) return "new";
  return "available";
}

// filters: {status: [], risk: [], source: [], compatible: bool}. OR inside a
// section, AND across sections, an empty section does not filter.
const statusOf = (row, now) => row.status || rowStatus(row.repo, row.app, now);

export function filterRows(rows, filters, query, now = Date.now()) {
  const q = String(query || "").trim().toLowerCase();
  const pick = (list, value) => !list?.length || list.includes(value);
  return rows.filter((row) => {
    const { repo, app } = row;
    if (!pick(filters.status, statusOf(row, now))) return false;
    if (!pick(filters.risk, riskOf(app))) return false;
    if (!pick(filters.source, repo.added_by || "author")) return false;
    if (filters.compatible && !app.compatible) return false;
    if (!q) return true;
    return [app.name, app.slug, app.description, repo.repository].some((v) => String(v || "").toLowerCase().includes(q));
  });
}

// [{key, label, rows}] in display order; rows keep their incoming order.
export function groupRows(rows, mode, now = Date.now()) {
  if (mode === "none") return [{ key: "all", label: "", rows }];
  const keyOf = {
    status: (r) => statusOf(r, now),
    risk: (r) => riskOf(r.app),
    repository: (r) => r.repo.repository,
  }[mode];
  const groups = new Map();
  for (const row of rows) {
    const key = keyOf(row);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  const order = {
    status: (k) => STATUS_ORDER.indexOf(k),
    risk: (k) => RISK_ORDER[k] ?? 3,
  }[mode];
  const keys = [...groups.keys()].sort((a, b) => (order ? order(a) - order(b) : a.localeCompare(b, undefined, { sensitivity: "base" })));
  const label = { status: (k) => STATUS_LABELS[k], risk: (k) => RISK_LABELS[k] || k, repository: (k) => k }[mode];
  return keys.map((key) => ({ key, label: label(key), rows: groups.get(key) }));
}

// rows: [{repo, app}]; repositories without stars or date sort last.
export function sortRows(rows, mode, now = Date.now()) {
  const compare = {
    stars: (a, b) => (b.repo.stars ?? -1) - (a.repo.stars ?? -1),
    updated: (a, b) => time(b.repo.updated_at) - time(a.repo.updated_at),
    risk: (a, b) => RISK_ORDER[riskOf(a.app)] - RISK_ORDER[riskOf(b.app)],
    status: (a, b) => STATUS_ORDER.indexOf(statusOf(a, now)) - STATUS_ORDER.indexOf(statusOf(b, now)),
    repository: (a, b) => a.repo.repository.localeCompare(b.repo.repository, undefined, { sensitivity: "base" }),
    name: () => 0,
  }[mode] || (() => 0);
  return [...rows].sort((a, b) => compare(a, b) || byName(a, b));
}

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

const COLUMNS = {
  icon: "Icon",
  repository: "Repository",
  stars: "Stars",
  activity: "Activity",
  risk: "Risk",
  status: "Status",
};
const GROUPS = { status: "Status", risk: "Risk", repository: "Repository", none: "Don't group" };
const FILTER_SECTIONS = {
  status: { label: "Status", options: STATUS_LABELS },
  risk: { label: "Risk", options: { high: "High", medium: "Medium", low: "Low" } },
  source: { label: "Source", options: { author: "Added by the author", catalog: "Added by the catalog" } },
};

const REL_FMT = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
const NUM_FMT = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 2 });
// Icon URLs that failed once (404): never requested again during this session.
const brokenIcons = new Set();

const relTime = (value) => {
  const t = Date.parse(value || "");
  if (Number.isNaN(t)) return "–";
  const fmt = REL_FMT;
  const steps = [[60, "second"], [60, "minute"], [24, "hour"], [7, "day"], [4.345, "week"], [12, "month"], [Infinity, "year"]];
  let v = (t - Date.now()) / 1000;
  for (const [n, unit] of steps) {
    if (Math.abs(v) < n) return fmt.format(Math.round(v), unit);
    v /= n;
  }
  return "–";
};
const compact = (n) => (typeof n === "number" ? NUM_FMT.format(n) : "–");

const store = {
  get(key, fallback) {
    try {
      const raw = localStorage.getItem(`community-apps-${key}`);
      return raw === null ? fallback : JSON.parse(raw);
    } catch (err) {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(`community-apps-${key}`, JSON.stringify(value));
    } catch (err) {
      // storage unavailable: the setting lasts for this page only
    }
  },
};

class CommunityAppsPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._error = null;
    this._loading = false;
    this._tab = "discover";
    this._query = "";
    this._filters = { ...defaultFilters(), ...store.get("filters", {}) };
    this._sort = store.get("sort2", "stars");
    if (!(this._sort in SORTS)) this._sort = "stars";
    this._group = store.get("group", "status");
    if (!(this._group in GROUPS)) this._group = "status";
    this._columns = { ...Object.fromEntries(Object.keys(COLUMNS).map((c) => [c, true])), ...store.get("columns", {}) };
    this._filtersOpen = store.get("filtersOpen", false);
    this._collapsed = new Set();
    this._menuOpen = null; // "group" | "sort" | null
    this._customizing = false;
    this._selected = null; // {repository, slug}
    this._confirming = null; // repository awaiting high-risk confirmation
    this._busy = null;
    this._added = {}; // repository -> {apps:[store slugs]} | {error}
    this._readmes = {}; // "repo|slug" -> {state: loading|ok|none, text, url}
    // Registered once: a broken icon is remembered and removed (error does not bubble).
    this.shadowRoot.addEventListener("error", (e) => {
      const img = e.target;
      if (img?.tagName === "IMG" && img.dataset.icon) {
        brokenIcons.add(img.dataset.icon);
        img.remove();
      }
    }, true);
    // Registered once: a click outside an open menu closes it.
    this.shadowRoot.addEventListener("click", (e) => {
      if (!this._menuOpen) return;
      const path = e.composedPath();
      if (path.some((n) => n.classList?.contains("menu") || n.dataset?.menu)) return;
      this._menuOpen = null;
      this._render();
    });
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
    } catch (err) {
      if (err?.code === "confirmation_required") {
        this._confirming = repository;
      } else {
        this._added[repository] = { error: err?.message || String(err) };
      }
      this._busy = null;
      this._render();
      return;
    }
    // The repository is added; a failed refresh only means the list is stale.
    try {
      this._data = await this._hass.callWS({ type: "community_apps/list" });
    } catch (err) {
      this._error = null;
    }
    this._busy = null;
    this._render();
  }

  _allRows() {
    const rows = [];
    for (const repo of this._data?.repositories || []) {
      if (repo.status === "removed") continue;
      for (const app of repo.scan?.apps || []) {
        if (!app.error) rows.push({ repo, app, status: rowStatus(repo, app) });
      }
    }
    return rows;
  }

  _baseRows() {
    const all = this._allRows();
    return this._tab === "installed" ? all.filter((r) => r.app.installed) : all;
  }

  _stats(repo) {
    const parts = [];
    if (typeof repo.stars === "number") parts.push(`★ ${repo.stars.toLocaleString()}`);
    if (repo.updated_at) parts.push(`updated ${esc(fmtDate(repo.updated_at))}`);
    return parts.join(" · ");
  }

  _riskChip(risk) {
    const r = risk in RISK_ORDER ? risk : "low";
    return `<span class="chip risk-${r}">${r} risk</span>`;
  }

  _statusChip(repo, app, status = rowStatus(repo, app)) {
    const cls = { flagged: "flagged", installed: "info", added: "info", new: "new", available: "muted" }[status];
    return `<span class="chip ${cls}">${esc(STATUS_LABELS[status])}</span>`;
  }

  _badges(repo, app) {
    const out = [this._statusChip(repo, app)];
    if (!app.compatible) out.push('<span class="chip muted">not for this system</span>');
    if (repo.added_by === "catalog") out.push('<span class="chip muted">added by the catalog</span>');
    return out.join("");
  }

  _icon(repo, app) {
    const url = iconUrl(repo, app);
    const fallback = `<span class="glyph">${esc((app.name || "?").slice(0, 1).toUpperCase())}</span>`;
    if (!url || brokenIcons.has(url)) return `<span class="icon">${fallback}</span>`;
    // loading=lazy: only icons of visible rows are requested.
    return `<span class="icon">${fallback}<img src="${esc(url)}" data-icon="${esc(url)}" alt="" loading="lazy" referrerpolicy="no-referrer"></span>`;
  }

  // ---- tabs -------------------------------------------------------------

  _tabsBar() {
    const installed = this._allRows().filter((r) => r.app.installed).length;
    const tab = (id, icon, label, extra = "") =>
      `<button class="tab ${this._tab === id && !this._selected ? "active" : ""}" data-tab="${id}"><span class="tab-icon">${icon}</span>${label}${extra}</button>`;
    return `
      <nav class="tabs">
        ${tab("discover", "◎", "Discover")}
        ${tab("browse", "▦", "Browse")}
        ${tab("installed", "✓", "Installed", installed ? `<span class="count">${installed}</span>` : "")}
      </nav>`;
  }

  _discoverView() {
    const rows = this._allRows().filter((r) => !this._filters.compatible || r.app.compatible);
    // At most two apps per repository, so one big repository does not fill a list.
    const top = (sorted, n = 6) => {
      const seen = {};
      return sorted.filter((r) => (seen[r.repo.repository] = (seen[r.repo.repository] || 0) + 1) <= 2).slice(0, n);
    };
    const byReview = [...rows].sort((a, b) => time(b.repo.reviewed?.at) - time(a.repo.reviewed?.at) || byName(a, b));
    const section = (title, list, seeAll) => `
      <section class="disc">
        <div class="disc-head"><h2>${title}</h2>${seeAll ? `<button class="link" data-seeall="${seeAll}">See all</button>` : ""}</div>
        <div class="disc-list">${list.map((r) => this._discRow(r)).join("") || '<p class="empty pad">Nothing yet.</p>'}</div>
      </section>`;
    return `
      <div class="discover">
        <h1 class="hero">Apps made by the community</h1>
        <p class="hint">Third-party apps, listed after a maintainer read an automated scan report. Open one to see what it can do before adding its repository.</p>
        <p class="disclaimer">No warranty. Apps are third-party software; you install them at your own risk. Being listed is not an endorsement.</p>
        ${section("Popular", top(sortRows(rows, "stars")), "stars")}
        ${section("Recently updated", top(sortRows(rows, "updated")), "updated")}
        ${section("New in the catalog", top(byReview), "")}
      </div>`;
  }

  _discRow({ repo, app }) {
    const installed = Boolean(app.installed);
    return `
      <button class="disc-row" data-repo="${esc(repo.repository)}" data-slug="${esc(app.slug)}">
        ${this._icon(repo, app)}
        <span class="cell-name"><span class="name">${esc(app.name)} ${this._riskChip(app.risk)}</span><span class="desc1">${esc(app.description || repo.repository)}</span></span>
        <span class="disc-meta">${installed ? '<span class="chip info">Installed</span>' : ""}${typeof repo.stars === "number" ? `<span>★ ${compact(repo.stars)}</span>` : ""}</span>
      </button>`;
  }

  // ---- browse / installed table -----------------------------------------

  _toolbar(count) {
    const active = ["status", "risk", "source"].reduce((n, k) => n + (this._filters[k]?.length || 0), 0) + (this._filters.compatible ? 1 : 0);
    const menu = (id, label, options, current, extra = "") => `
      <div class="menu-wrap">
        <button class="pill" data-menu="${id}">${label} ▾</button>
        ${this._menuOpen === id ? `<div class="menu">${Object.entries(options).map(([v, l]) => `<button class="menu-item ${current === v ? "sel" : ""}" data-${id}="${v}">${esc(l)}</button>`).join("")}${extra}</div>` : ""}
      </div>`;
    const groupExtra = this._group === "none" ? "" : '<div class="menu-sep"></div><button class="menu-item" data-collapse="all">Collapse all</button><button class="menu-item" data-collapse="none">Expand all</button>';
    return `
      <div class="toolbar">
        ${this._tab === "browse" ? `<button class="pill ${this._filtersOpen ? "on" : ""}" id="filters-toggle">☰ Filters${active ? `<span class="count">${active}</span>` : ""}</button>` : ""}
        <input id="q" type="search" placeholder="Search ${count} apps" value="${esc(this._query)}" aria-label="Search apps">
        ${menu("group", `Group by ${this._group === "none" ? "nothing" : GROUPS[this._group]}`, GROUPS, this._group, groupExtra)}
        ${menu("sort", "Sort by", SORTS, this._sort)}
        <button class="pill square" id="customize" title="Customize columns" aria-label="Customize columns">⚙</button>
      </div>`;
  }

  _filterPane() {
    const sections = Object.entries(FILTER_SECTIONS)
      .map(([key, { label, options }]) => `
        <div class="fsec">
          <div class="fsec-title">${label}</div>
          ${Object.entries(options).map(([v, l]) => `<label class="fopt"><span>${esc(l)}</span><input type="checkbox" data-filter="${key}" value="${v}" ${this._filters[key]?.includes(v) ? "checked" : ""}></label>`).join("")}
        </div>`)
      .join("");
    return `
      <aside class="fpane">
        ${sections}
        <div class="fsec">
          <div class="fsec-title">System</div>
          <label class="fopt"><span>Only apps for this system</span><input type="checkbox" id="compat" ${this._filters.compatible ? "checked" : ""}></label>
        </div>
        <button class="link" id="clear-filters">Clear filters</button>
      </aside>`;
  }

  _tableView() {
    const base = this._baseRows();
    const filters = this._tab === "installed" ? { compatible: false } : this._filters;
    const rows = sortRows(filterRows(base, filters, this._query), this._sort);
    const groups = groupRows(rows, this._group);
    const cols = this._columns;
    const template = [cols.icon ? "44px" : null, "minmax(180px, 3fr)", cols.repository ? "minmax(120px, 1.4fr)" : null,
      cols.stars ? "80px" : null, cols.activity ? "120px" : null, cols.risk ? "110px" : null, cols.status ? "160px" : null]
      .filter(Boolean).join(" ");
    // Phones keep only the visible icon, name and risk columns.
    const narrow = [cols.icon ? "44px" : null, "1fr", cols.risk ? "110px" : null].filter(Boolean).join(" ");
    const gridVars = `--cols:${template};--cols-narrow:${narrow}`;
    const head = `
      <div class="trow thead" style="${gridVars}">
        ${cols.icon ? "<span></span>" : ""}<span>App</span>${cols.repository ? '<span class="c-repo">Repository</span>' : ""}
        ${cols.stars ? '<span class="num">Stars</span>' : ""}${cols.activity ? '<span class="num c-act">Activity</span>' : ""}
        ${cols.risk ? "<span>Risk</span>" : ""}${cols.status ? '<span class="c-status">Status</span>' : ""}
      </div>`;
    const line = ({ repo, app, status }) => `
      <button class="trow" style="${gridVars}" data-repo="${esc(repo.repository)}" data-slug="${esc(app.slug)}">
        ${cols.icon ? this._icon(repo, app) : ""}
        <span class="cell-name"><span class="name">${esc(app.name)}</span><span class="desc1">${esc(app.description || "")}</span></span>
        ${cols.repository ? `<span class="muted c-repo ellip">${esc(repo.repository)}</span>` : ""}
        ${cols.stars ? `<span class="num">${compact(repo.stars)}</span>` : ""}
        ${cols.activity ? `<span class="num muted c-act">${esc(relTime(repo.updated_at))}</span>` : ""}
        ${cols.risk ? `<span>${this._riskChip(app.risk)}</span>` : ""}
        ${cols.status ? `<span class="c-status">${this._statusChip(repo, app, status)}</span>` : ""}
      </button>`;
    const body = groups
      .map((g) => {
        if (this._group === "none") return g.rows.map(line).join("");
        const collapsed = this._collapsed.has(g.key);
        return `
          <button class="ghead" data-group="${esc(g.key)}"><span class="chev">${collapsed ? "▸" : "▾"}</span>${esc(g.label)}<span class="gcount">${g.rows.length}</span></button>
          ${collapsed ? "" : g.rows.map(line).join("")}`;
      })
      .join("");
    const showPane = this._tab === "browse" && this._filtersOpen;
    const empty = this._tab === "installed" ? "No app from the catalog is installed." : "No app matches these filters.";
    return `
      ${this._toolbar(base.length)}
      <div class="browse ${showPane ? "with-pane" : ""}">
        ${showPane ? this._filterPane() : ""}
        <div class="table">${head}${body || `<p class="empty pad">${empty}</p>`}</div>
      </div>
      ${this._customizing ? this._customizeDialog() : ""}`;
  }

  _customizeDialog() {
    return `
      <div class="overlay" id="overlay">
        <div class="dialog" role="dialog" aria-label="Customize">
          <div class="dialog-head"><button class="link" id="close-customize" aria-label="Close">✕</button><h2>Customize</h2></div>
          <label class="copt disabled"><span>App name</span><input type="checkbox" checked disabled></label>
          ${Object.entries(COLUMNS).map(([c, l]) => `<label class="copt"><span>${l}</span><input type="checkbox" data-col="${c}" ${this._columns[c] ? "checked" : ""}></label>`).join("")}
          <div class="dialog-actions"><button class="link" id="restore-columns">Restore defaults</button><button class="button" id="done-customize">Done</button></div>
        </div>
      </div>`;
  }

  _detailView() {
    const { repo, app } = this._selectedRow();
    const perms = app.permissions?.length
      ? `<ul>${app.permissions.map((p) => `<li><code>${esc(p)}</code> ${esc(describePermission(p))}</li>`).join("")}</ul>`
      : "<p>No sensitive permission requested.</p>";
    const domains = app.domains?.length
      ? `<ul>${app.domains.map((d) => `<li><code>${esc(d)}</code></li>`).join("")}</ul>`
      : "<p>None found.</p>";
    const dynamic = {
      started: "The app was started for a few minutes in an isolated network; the domains above include what it looked up.",
      failed: "The app did not keep running without its configuration, so only domains found in its code are listed.",
      skipped: "The app was not started (architecture not tested, or the time budget for this repository was used by riskier apps), so only domains found in its code are listed.",
    }[app.dynamic || "skipped"];
    const reviewed = repo.reviewed
      ? `Listed on ${esc(fmtDate(repo.reviewed.at))} by ${esc(repo.reviewed.by)} after reading the scan report. Last scan ${esc(fmtDate(repo.scan?.at))}.`
      : "";
    const entryPath = repo.repository.toLowerCase();
    return `
      <button class="link back" id="back">← Back</button>
      <div class="card detail">
        <div class="row"><h2>${esc(app.name)}</h2>${this._riskChip(app.risk)}</div>
        <div class="repo">${esc(repo.repository)}${app.version ? ` · version ${esc(app.version)}` : ""} · ${app.image === "prebuilt" ? "prebuilt image" : "built from source on your system"}</div>
        ${this._stats(repo) ? `<div class="repo">${this._stats(repo)}</div>` : ""}
        <div class="badges">${this._badges(repo, app)}</div>
        ${repo.status === "flagged" ? '<p class="warn">This repository changed since it was reviewed (new permissions, higher risk or new domains). It is back in review; adding it is paused.</p>' : ""}
        ${app.description ? `<p class="lead">${esc(app.description)}</p>` : ""}
        <h3>What it can do</h3>${perms}
        <h3>Domains contacted</h3>${domains}<p class="hint">${esc(dynamic)} Connections to raw IP addresses are not detected.</p>
        <h3>Listing</h3>
        <p>${reviewed}</p>
        <p class="hint">The scan report is read when a repository enters the catalog. Updates reach you before the nightly rescan. The signals above do not prove an app is harmless.</p>
        <p class="disclaimer">No warranty. Apps are third-party software; you install them at your own risk. Being listed is not an endorsement.</p>
        <p class="links">
          <a href="https://github.com/${esc(repo.repository)}" target="_blank" rel="noopener noreferrer">Repository</a>
          <a href="https://github.com/Gluxur/ha-community-apps/blob/main/catalog/repositories/${esc(entryPath)}.yaml" target="_blank" rel="noopener noreferrer">Catalog entry</a>
        </p>
        ${this._actions(repo, app)}
        <h3>README</h3>
        <div class="readme" id="readme">${this._readmeStatus(repo, app)}</div>
      </div>`;
  }

  _readmeStatus(repo, app) {
    const entry = this._readmes[`${repo.repository}|${app.slug}`];
    if (!entry || entry.state === "loading") return '<p class="hint">Loading the README from GitHub…</p>';
    if (entry.state === "none") return '<p class="hint">This app has no README.</p>';
    return `<p class="hint">From <a href="${esc(entry.url)}" target="_blank" rel="noopener noreferrer">GitHub</a>, written by the app's author.</p><div id="readme-body"></div>`;
  }

  async _loadReadme(repo, app) {
    const key = `${repo.repository}|${app.slug}`;
    if (this._readmes[key]) return;
    this._readmes[key] = { state: "loading" };
    for (const url of readmeUrls(repo, app)) {
      try {
        const resp = await fetch(url, { credentials: "omit" });
        if (resp.ok) {
          const text = (await resp.text()).slice(0, 200000);
          this._readmes[key] = { state: "ok", text, url: url.replace("https://raw.githubusercontent.com/", "https://github.com/").replace("/HEAD/", "/blob/HEAD/") };
          this._render();
          return;
        }
      } catch (err) {
        // try the next file
      }
    }
    this._readmes[key] = { state: "none" };
    this._render();
  }

  async _ensureMarkdown() {
    if (customElements.get("ha-markdown") || this._markdownTried) return;
    this._markdownTried = true;
    try {
      // ha-markdown is lazy-loaded by Home Assistant; creating a markdown card loads it.
      const helpers = await window.loadCardHelpers?.();
      await helpers?.createCardElement({ type: "markdown", content: "" });
      await Promise.race([customElements.whenDefined("ha-markdown"), new Promise((r) => setTimeout(r, 3000))]);
    } catch (err) {
      // fall back to plain text
    }
    if (customElements.get("ha-markdown")) this._render();
  }

  _mountReadme(repo, app) {
    const entry = this._readmes[`${repo.repository}|${app.slug}`];
    const slot = this.shadowRoot.getElementById("readme-body");
    if (!entry || entry.state !== "ok" || !slot) return;
    this._ensureMarkdown();
    if (customElements.get("ha-markdown")) {
      // Home Assistant's renderer sanitizes the HTML of third-party Markdown.
      const md = document.createElement("ha-markdown");
      md.breaks = false;
      md.content = entry.text;
      slot.appendChild(md);
    } else {
      const pre = document.createElement("pre");
      pre.textContent = entry.text;
      slot.appendChild(pre);
    }
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
    // A selected app that left the catalog (refresh) falls back to the current tab.
    if (this._selected && !this._selectedRow()) this._selected = null;
    let body;
    if (this._error) body = `<div class="banner">Could not load the catalog: ${esc(this._error)} <button class="link" id="retry">Retry</button></div>`;
    else if (!this._data) body = '<p class="empty pad">Loading…</p>';
    else if (this._selected) body = banner + `<div class="page">${this._detailView()}</div>`;
    else if (this._tab === "discover") body = banner + `<div class="page">${this._discoverView()}</div>`;
    else body = banner + this._tableView();

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; min-height: 100vh; background: var(--primary-background-color); color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, sans-serif); font-size: 14px; line-height: 1.45; }
        * { box-sizing: border-box; }
        header { position: sticky; top: 0; z-index: 3; display: flex; align-items: center; gap: 8px; height: 56px; padding: 0 12px; background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, #fff); border-bottom: 1px solid var(--divider-color); }
        header h1 { font-size: 20px; font-weight: 400; margin: 0 8px 0 0; white-space: nowrap; }
        .tabs { display: flex; flex: 1; justify-content: center; height: 100%; }
        .tab { display: flex; align-items: center; gap: 6px; height: 100%; padding: 0 16px; background: none; border: none; border-bottom: 2px solid transparent; color: inherit; font: inherit; cursor: pointer; opacity: .85; }
        .tab.active { color: var(--primary-color); border-bottom-color: var(--primary-color); opacity: 1; }
        .tab-icon { font-size: 15px; }
        .count { margin-left: 6px; font-size: 11px; padding: 0 6px; border-radius: 8px; background: var(--primary-color); color: var(--text-primary-color, #fff); }
        .refresh { background: none; border: 1px solid currentColor; border-radius: 16px; padding: 4px 12px; color: inherit; font: inherit; cursor: pointer; white-space: nowrap; }
        .page { max-width: 1000px; margin: 0 auto; padding: 16px; }
        .pad { padding: 16px; }
        .toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 10px 12px; border-bottom: 1px solid var(--divider-color); }
        .pill { display: inline-flex; align-items: center; gap: 4px; padding: 7px 12px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); font: inherit; cursor: pointer; white-space: nowrap; }
        .pill.on { border-color: var(--primary-color); color: var(--primary-color); }
        .pill.square { padding: 7px 10px; }
        input[type=search] { flex: 1 1 220px; min-width: 0; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); font: inherit; }
        .menu-wrap { position: relative; }
        .menu { position: absolute; right: 0; top: calc(100% + 4px); z-index: 4; min-width: 180px; padding: 4px 0; border-radius: 8px; border: 1px solid var(--divider-color); background: var(--card-background-color); box-shadow: 0 4px 16px rgba(0,0,0,.25); }
        .menu-item { display: block; width: 100%; padding: 9px 16px; text-align: left; background: none; border: none; color: var(--primary-text-color); font: inherit; cursor: pointer; }
        .menu-item:hover { background: var(--secondary-background-color, rgba(127,127,127,.12)); }
        .menu-item.sel { color: var(--primary-color); }
        .menu-sep { border-top: 1px solid var(--divider-color); margin: 4px 0; }
        .browse { display: grid; grid-template-columns: 1fr; }
        .browse.with-pane { grid-template-columns: 240px 1fr; }
        .fpane { border-right: 1px solid var(--divider-color); padding: 8px 0; }
        .fsec { padding: 4px 0 8px; border-bottom: 1px solid var(--divider-color); }
        .fsec-title { padding: 8px 16px; font-weight: 500; }
        .fopt { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 6px 16px; cursor: pointer; }
        #clear-filters { margin: 8px 16px; }
        .table { min-width: 0; }
        .trow { display: grid; grid-template-columns: var(--cols); align-items: center; gap: 12px; width: 100%; min-height: 56px; padding: 6px 12px; text-align: left; background: none; border: none; border-bottom: 1px solid var(--divider-color); color: inherit; font: inherit; cursor: pointer; }
        button.trow:hover { background: var(--secondary-background-color, rgba(127,127,127,.08)); }
        .thead { min-height: 44px; font-weight: 500; cursor: default; position: sticky; top: 56px; z-index: 2; background: var(--primary-background-color); }
        .ghead { display: flex; align-items: center; gap: 8px; width: 100%; padding: 12px; background: none; border: none; border-bottom: 1px solid var(--divider-color); color: inherit; font: inherit; font-weight: 500; cursor: pointer; text-align: left; }
        .chev { width: 14px; }
        .gcount { color: var(--secondary-text-color); font-weight: 400; }
        .cell-name { display: flex; flex-direction: column; min-width: 0; }
        .name { font-weight: 500; overflow-wrap: anywhere; }
        .desc1 { color: var(--primary-color); font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .ellip { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .num { text-align: right; }
        .icon { position: relative; width: 36px; height: 36px; display: inline-flex; }
        .icon img { position: absolute; inset: 0; width: 36px; height: 36px; object-fit: contain; border-radius: 6px; background: var(--card-background-color); }
        .glyph { width: 36px; height: 36px; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; background: var(--secondary-background-color, rgba(127,127,127,.2)); font-weight: 500; }
        .discover .hero { font-size: 28px; font-weight: 600; margin: 8px 0 4px; }
        .disc { margin-top: 24px; }
        .disc-head { display: flex; justify-content: space-between; align-items: baseline; }
        .disc-head h2 { font-size: 18px; font-weight: 500; margin: 0 0 8px; }
        .disc-list { border: 1px solid var(--divider-color); border-radius: 12px; overflow: hidden; background: var(--card-background-color); }
        .disc-row { display: grid; grid-template-columns: 44px 1fr auto; align-items: center; gap: 12px; width: 100%; padding: 10px 14px; background: none; border: none; border-bottom: 1px solid var(--divider-color); color: inherit; font: inherit; text-align: left; cursor: pointer; }
        .disc-row:last-child { border-bottom: none; }
        .disc-row:hover { background: var(--secondary-background-color, rgba(127,127,127,.08)); }
        .disc-meta { display: flex; gap: 10px; align-items: center; color: var(--secondary-text-color); white-space: nowrap; }
        .card { background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 12px; padding: 12px 14px; text-align: left; color: inherit; font: inherit; }
        .row { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
        .repo { color: var(--secondary-text-color); font-size: 13px; margin-top: 2px; overflow-wrap: anywhere; }
        .badges { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
        .chip { display: inline-block; font-size: 12px; font-weight: 400; padding: 1px 8px; border-radius: 10px; white-space: nowrap; border: 1px solid var(--divider-color); }
        .risk-low { color: var(--success-color); border-color: var(--success-color); }
        .risk-medium { color: var(--warning-color); border-color: var(--warning-color); }
        .risk-high { color: var(--error-color); border-color: var(--error-color); }
        .flagged { color: var(--warning-color); border-color: var(--warning-color); }
        .info { color: var(--primary-color); border-color: var(--primary-color); }
        .new { color: var(--success-color); border-color: var(--success-color); }
        .muted { color: var(--secondary-text-color); }
        .hint { color: var(--secondary-text-color); font-size: 13px; }
        .disclaimer { font-size: 13px; font-weight: 500; border-left: 3px solid var(--warning-color); padding: 4px 10px; }
        .empty { color: var(--secondary-text-color); }
        .banner, .warn { border-left: 4px solid var(--warning-color); padding: 8px 12px; background: var(--card-background-color); margin: 12px; }
        .detail h2 { margin: 0; font-size: 22px; font-weight: 400; overflow-wrap: anywhere; }
        .detail h3 { font-size: 15px; margin: 18px 0 6px; }
        .detail ul { padding-left: 20px; margin: 4px 0; }
        .detail li { margin: 4px 0; overflow-wrap: anywhere; }
        code { font-size: 12px; background: var(--secondary-background-color, rgba(127,127,127,.15)); padding: 1px 4px; border-radius: 4px; }
        .links { display: flex; gap: 16px; }
        .lead { font-size: 15px; margin: 10px 0 0; }
        .readme { border-top: 1px solid var(--divider-color); padding-top: 4px; overflow-wrap: anywhere; }
        .readme pre { white-space: pre-wrap; font-size: 13px; }
        a { color: var(--primary-color); }
        .button { display: inline-block; margin-top: 12px; padding: 10px 16px; border-radius: 8px; border: none; background: var(--primary-color); color: var(--text-primary-color, #fff); font: inherit; cursor: pointer; text-decoration: none; }
        .button[disabled] { opacity: .6; cursor: default; }
        .button.danger { background: var(--error-color); }
        .link { background: none; border: none; color: var(--primary-color); font: inherit; cursor: pointer; padding: 4px 0; }
        .back { margin-bottom: 8px; }
        .confirm { margin-top: 12px; border: 1px solid var(--error-color); border-radius: 8px; padding: 8px 12px; }
        .overlay { position: fixed; inset: 0; z-index: 10; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,.5); padding: 16px; }
        .dialog { width: 100%; max-width: 360px; border-radius: 16px; background: var(--card-background-color); padding: 12px 0; box-shadow: 0 8px 32px rgba(0,0,0,.4); }
        .dialog-head { display: flex; align-items: center; gap: 12px; padding: 4px 20px 8px; }
        .dialog-head h2 { margin: 0; font-size: 20px; font-weight: 400; }
        .copt { display: flex; justify-content: space-between; align-items: center; padding: 8px 20px; cursor: pointer; }
        .copt.disabled { color: var(--secondary-text-color); cursor: default; }
        .dialog-actions { display: flex; justify-content: flex-end; align-items: center; gap: 16px; padding: 12px 20px 4px; }
        .dialog-actions .button { margin-top: 0; }
        @media (max-width: 760px) {
          header h1 { display: none; }
          .tab { padding: 0 8px; }
          .tab-icon, .rlabel { display: none; }
          .refresh { padding: 4px 10px; }
          .browse.with-pane { grid-template-columns: 1fr; }
          .fpane { border-right: none; border-bottom: 1px solid var(--divider-color); }
          .trow { grid-template-columns: var(--cols-narrow); }
          .trow .c-repo, .trow .num, .trow .c-status { display: none; }
          .thead { top: 56px; }
        }
      </style>
      <header>
        <span id="menu"></span><h1>Community Apps</h1>
        ${this._data ? this._tabsBar() : '<span class="tabs"></span>'}
        <button class="refresh" id="refresh" ${this._loading ? "disabled" : ""}>↻<span class="rlabel"> ${this._loading ? "Refreshing…" : "Refresh"}</span></button>
      </header>
      ${body}`;
    this._wire();
  }

  _selectedRow() {
    const repo = (this._data?.repositories || []).find((r) => r.repository === this._selected?.repository);
    const app = repo?.scan?.apps?.find((a) => a.slug === this._selected?.slug);
    return repo && app ? { repo, app } : null;
  }

  _open(el) {
    this._selected = { repository: el.dataset.repo, slug: el.dataset.slug };
    this._menuOpen = null;
    this._render();
    window.scrollTo(0, 0);
  }

  _saveFilters() {
    store.set("filters", this._filters);
    this._render();
  }

  _wire() {
    const root = this.shadowRoot;
    const on = (sel, event, fn) => root.querySelectorAll(sel).forEach((el) => el.addEventListener(event, (e) => fn(el, e)));
    const slot = root.getElementById("menu");
    if (slot && customElements.get("ha-menu-button")) {
      this._menu = this._menu || document.createElement("ha-menu-button");
      this._menu.hass = this._hass;
      this._menu.narrow = this._narrow;
      slot.appendChild(this._menu);
    }
    on("#refresh, #retry", "click", () => this._load(true));
    on(".tab", "click", (el) => {
      this._tab = el.dataset.tab;
      this._selected = null;
      this._confirming = null;
      this._menuOpen = null;
      this._render();
    });
    on("[data-seeall]", "click", (el) => {
      this._tab = "browse";
      this._sort = el.dataset.seeall;
      store.set("sort2", this._sort);
      this._render();
    });
    on("button.trow, .disc-row", "click", (el) => this._open(el));
    const q = root.getElementById("q");
    q?.addEventListener("input", (e) => {
      this._query = e.target.value;
      if (e.isComposing) return; // IME: wait for compositionend
      clearTimeout(this._searchTimer);
      // Debounced: one render after typing pauses, not one per key.
      this._searchTimer = setTimeout(() => {
        const input = this.shadowRoot.getElementById("q");
        const pos = input?.selectionStart ?? this._query.length;
        this._render();
        const again = this.shadowRoot.getElementById("q");
        again?.focus();
        again?.setSelectionRange(pos, pos);
      }, 200);
    });
    q?.addEventListener("compositionend", (e) => {
      q.dispatchEvent(new Event("input"));
    });
    on("#filters-toggle", "click", () => {
      this._filtersOpen = !this._filtersOpen;
      store.set("filtersOpen", this._filtersOpen);
      this._render();
    });
    on("[data-filter]", "change", (el) => {
      const list = new Set(this._filters[el.dataset.filter] || []);
      if (el.checked) list.add(el.value);
      else list.delete(el.value);
      this._filters = { ...this._filters, [el.dataset.filter]: [...list] };
      this._saveFilters();
    });
    on("#compat", "change", (el) => {
      this._filters = { ...this._filters, compatible: el.checked };
      this._saveFilters();
    });
    on("#clear-filters", "click", () => {
      this._filters = defaultFilters();
      this._saveFilters();
    });
    on("[data-menu]", "click", (el, e) => {
      e.stopPropagation();
      this._menuOpen = this._menuOpen === el.dataset.menu ? null : el.dataset.menu;
      this._render();
    });
    on("[data-group]", "click", (el) => {
      if (el.classList.contains("ghead")) {
        if (this._collapsed.has(el.dataset.group)) this._collapsed.delete(el.dataset.group);
        else this._collapsed.add(el.dataset.group);
      } else {
        this._group = el.dataset.group in GROUPS ? el.dataset.group : "status";
        this._collapsed.clear();
        store.set("group", this._group);
        this._menuOpen = null;
      }
      this._render();
    });
    on("[data-collapse]", "click", (el) => {
      this._collapsed = el.dataset.collapse === "all" ? new Set(groupRows(this._baseRows(), this._group).map((g) => g.key)) : new Set();
      this._menuOpen = null;
      this._render();
    });
    on("[data-sort]", "click", (el) => {
      this._sort = el.dataset.sort in SORTS ? el.dataset.sort : "stars";
      store.set("sort2", this._sort);
      this._menuOpen = null;
      this._render();
    });
    on("#customize", "click", () => {
      this._customizing = true;
      this._menuOpen = null;
      this._render();
    });
    on("[data-col]", "change", (el) => {
      this._columns = { ...this._columns, [el.dataset.col]: el.checked };
      store.set("columns", this._columns);
      this._render();
    });
    on("#restore-columns", "click", () => {
      this._columns = Object.fromEntries(Object.keys(COLUMNS).map((c) => [c, true]));
      store.set("columns", this._columns);
      this._render();
    });
    on("#close-customize, #done-customize", "click", () => {
      this._customizing = false;
      this._render();
    });
    on("#overlay", "click", (el, e) => {
      if (e.target === el) {
        this._customizing = false;
        this._render();
      }
    });
    on("#back", "click", () => {
      this._selected = null;
      this._confirming = null;
      this._render();
    });
    if (this._selected) {
      const repo = (this._data?.repositories || []).find((r) => r.repository === this._selected.repository);
      const app = repo?.scan?.apps?.find((a) => a.slug === this._selected.slug);
      if (repo && app) {
        this._loadReadme(repo, app);
        this._mountReadme(repo, app);
      }
    }
    const current = this._selected?.repository;
    on("#add", "click", () => this._add(current, false));
    on("#confirm-add", "click", () => this._add(current, true));
    on("#cancel-add", "click", () => {
      this._confirming = null;
      this._render();
    });
  }
}

customElements.define("community-apps-panel", CommunityAppsPanel);

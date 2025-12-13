import { getAll, getByKey, getAllByIndex, getMeta } from "./idb.js";

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function nl2br(s) {
  const safe = esc(s);
  return safe.replaceAll("\n", "<br>");
}

function qs() {
  return new URLSearchParams(window.location.search);
}

function setQuerySiteId(siteId) {
  const url = new URL(window.location.href);
  if (siteId) url.searchParams.set("site", String(siteId));
  else url.searchParams.delete("site");
  history.pushState({}, "", url);
}

function updateOnlineUI() {
  const online = navigator.onLine;
  const dot = document.getElementById("netDot");
  const txt = document.getElementById("netText");
  if (dot) dot.textContent = online ? "🟢" : "🔴";
  if (txt) txt.textContent = online ? "online" : "offline";
}

async function loadLastSync() {
  const v = await getMeta("last_sync");
  const el = document.getElementById("lastSync");
  if (el) el.textContent = v || "—";
}

function setBusy(isBusy) {
  const btn = document.getElementById("syncBtn");
  if (!btn) return;
  btn.disabled = isBusy;
  btn.textContent = isBusy ? "SYNC…" : "SYNC";
}

async function doSyncCatalog() {
  if (!navigator.onLine) {
    alert("Brak internetu — nie mogę zsynchronizować teraz.");
    return;
  }

  setBusy(true);
  try {
    // używamy tej samej logiki co na stronie /pwa/ (pwa.js)
    const mod = await import("./pwa.js");
    // pwa.js ma prywatne doSyncCatalog, więc tutaj robimy prosto:
    const resp = await fetch("/api/pwa/catalog/dump/", {
      method: "GET",
      headers: { "Accept": "application/json" },
      credentials: "same-origin",
      cache: "no-store",
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    // zapis jak w pwa.js (snapshot)
    const { clearStore, putMany, setMeta } = await import("./idb.js");
    await clearStore("sites");
    await clearStore("systems");
    await putMany("sites", data.sites || []);
    await putMany("systems", data.systems || []);

    const stamp = new Date().toLocaleString("pl-PL");
    await setMeta("last_sync", stamp);
    await loadLastSync();

    alert(`SYNC OK ✅\nObiekty: ${data.sites?.length || 0}\nSystemy: ${data.systems?.length || 0}`);
    // po sync odśwież widok
    await render();
  } catch (e) {
    console.error(e);
    alert("SYNC nieudany ❌\n" + (e?.message || e));
  } finally {
    setBusy(false);
  }
}

async function renderList() {
  const root = document.getElementById("viewRoot");
  const searchBox = document.getElementById("searchBox");
  if (!root) return;

  const allSites = await getAll("sites");
  const q = (searchBox?.value || "").trim().toLowerCase();

  const filtered = !q
    ? allSites
    : allSites.filter((s) => {
        const hay = `${s.name ?? ""} ${s.street ?? ""} ${s.city ?? ""}`.toLowerCase();
        return hay.includes(q);
      });

  filtered.sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), "pl"));

  if (!filtered.length) {
    root.innerHTML = `<div class="alert alert-light border">Brak wyników.</div>`;
    return;
  }

  root.innerHTML = `
    <div class="d-grid gap-2">
      ${filtered
        .map(
          (s) => `
        <button class="card pwa-card text-start border-0" data-site="${esc(s.id)}" style="cursor:pointer;">
          <div class="card-body">
            <div class="fw-semibold">${esc(s.name)}</div>
            <div class="small pwa-muted">${esc(s.street)}${s.street && s.city ? ", " : ""}${esc(s.city)}</div>
          </div>
        </button>
      `
        )
        .join("")}
    </div>
  `;

  root.querySelectorAll("[data-site]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const siteId = Number(btn.getAttribute("data-site"));
      setQuerySiteId(siteId);
      await render();
    });
  });
}

async function renderDetail(siteId) {
  const root = document.getElementById("viewRoot");
  const searchBox = document.getElementById("searchBox");
  if (!root) return;

  const site = await getByKey("sites", siteId);
  if (!site) {
    root.innerHTML = `<div class="alert alert-warning border">Nie znaleziono obiektu w offline cache. Zrób SYNC.</div>`;
    return;
  }

  const systems = await getAllByIndex("systems", "by_site_id", siteId);
  systems.sort((a, b) => String(a.system_type || "").localeCompare(String(b.system_type || ""), "pl"));

  // na szczegółach nie potrzebujemy wyszukiwarki listy
  if (searchBox) searchBox.value = "";

  root.innerHTML = `
    <div class="card pwa-card mb-3">
      <div class="card-body">
        <div class="d-flex justify-content-between align-items-start gap-2">
          <div>
            <div class="h5 mb-1">${esc(site.name)}</div>
            <div class="small pwa-muted">
              ${esc(site.street)}${site.street && site.city ? ", " : ""}${esc(site.city)}
            </div>
          </div>
          <button class="btn btn-outline-secondary pwa-btn" id="backToList">Lista</button>
        </div>
      </div>
    </div>

    ${site.access_info ? `
      <div class="card pwa-card mb-3"><div class="card-body">
        <div class="fw-semibold mb-2">Informacje o dostępie</div>
        <div class="small">${nl2br(site.access_info)}</div>
      </div></div>
    ` : ""}

    ${site.technical_notes ? `
      <div class="card pwa-card mb-3"><div class="card-body">
        <div class="fw-semibold mb-2">Notatki techniczne</div>
        <div class="small">${nl2br(site.technical_notes)}</div>
      </div></div>
    ` : ""}

    <div class="card pwa-card"><div class="card-body">
      <div class="fw-semibold mb-2">Systemy na obiekcie</div>
      ${
        systems.length
          ? `<div class="d-grid gap-2">
              ${systems
                .map(
                  (x) => `
                <button class="btn btn-outline-secondary pwa-btn text-start" data-system="${esc(x.id)}">
                  <div class="fw-semibold">${esc(x.system_type)}</div>
                  <div class="small pwa-muted">${esc(x.name || "—")}</div>
                </button>
              `
                )
                .join("")}
            </div>
            <div class="small pwa-muted mt-2">Kliknij system, żeby podejrzeć dane (offline).</div>`
          : `<div class="alert alert-light border mb-0">Brak systemów.</div>`
      }
    </div></div>

    <div id="systemModal"></div>
  `;

  document.getElementById("backToList")?.addEventListener("click", async () => {
    setQuerySiteId(null);
    await render();
  });

  root.querySelectorAll("[data-system]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const systemId = Number(btn.getAttribute("data-system"));
      const sys = await getByKey("systems", systemId);
      const modalRoot = document.getElementById("systemModal");
      if (!modalRoot || !sys) return;

      modalRoot.innerHTML = `
        <div class="card pwa-card mt-3">
          <div class="card-body">
            <div class="d-flex justify-content-between align-items-start gap-2">
              <div>
                <div class="badge text-bg-info mb-2">${esc(sys.system_type)}</div>
                <div class="h6 mb-1">${esc(sys.name || "—")}</div>
              </div>
              <button class="btn btn-outline-secondary pwa-btn" id="closeSys">✕</button>
            </div>

            ${sys.location_info ? `<div class="mt-2"><div class="fw-semibold">Lokalizacja</div><div class="small">${nl2br(sys.location_info)}</div></div>` : ""}
            ${sys.access_data ? `<div class="mt-2"><div class="fw-semibold">Dostęp</div><div class="small">${nl2br(sys.access_data)}</div></div>` : ""}
            ${sys.procedures ? `<div class="mt-2"><div class="fw-semibold">Procedury</div><div class="small">${nl2br(sys.procedures)}</div></div>` : ""}
            ${sys.notes ? `<div class="mt-2"><div class="fw-semibold">Notatki</div><div class="small">${nl2br(sys.notes)}</div></div>` : ""}
          </div>
        </div>
      `;

      document.getElementById("closeSys")?.addEventListener("click", () => {
        modalRoot.innerHTML = "";
      });
    });
  });
}

async function render() {
  const site = qs().get("site");
  if (site) {
    await renderDetail(Number(site));
  } else {
    await renderList();
  }
}

export async function initPwaObjects() {
  updateOnlineUI();
  await loadLastSync();
  await render();

  window.addEventListener("online", updateOnlineUI);
  window.addEventListener("offline", updateOnlineUI);
  window.addEventListener("popstate", render);

  const searchBox = document.getElementById("searchBox");
  if (searchBox) {
    searchBox.addEventListener("input", () => {
      // tylko lista reaguje na wyszukiwanie
      if (!qs().get("site")) render();
    });
  }

  const syncBtn = document.getElementById("syncBtn");
  if (syncBtn) syncBtn.addEventListener("click", doSyncCatalog);
}

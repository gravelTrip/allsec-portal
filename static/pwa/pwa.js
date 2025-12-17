// core/static/pwa/pwa.js
import {
  clearStore, putMany, setMeta, getMeta, getAll, getByKey,
  putSrDraft, getSrDraft,
  putMpDraft, getMpDraft,
  enqueueOutbox, listOutbox, deleteOutbox
} from "./idb.js";

function $(id) {
  return document.getElementById(id);
}

async function pingServer(timeoutMs = 1500) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);

  try {
    const resp = await fetch("/api/pwa/ping/", {
      method: "GET",
      headers: { "Accept": "application/json" },
      credentials: "same-origin",
      cache: "no-store",
      signal: ctrl.signal,
    });
    return resp.ok;
  } catch (e) {
    return false;
  } finally {
    clearTimeout(t);
  }
}

async function updateOnlineUI() {
  const ok = await pingServer();

  if ($("netDot")) $("netDot").textContent = ok ? "🟢" : "🔴";
  if ($("netText")) $("netText").textContent = ok ? "online" : "offline";
}

async function loadLastSync() {
  const v = await getMeta("last_sync");
  if ($("lastSync")) $("lastSync").textContent = v || "—";
}

function setBusy(isBusy) {
  const btn = $("syncBtn");
  if (!btn) return;
  btn.disabled = isBusy;
  btn.textContent = isBusy ? "SYNC…" : "SYNC";
}

async function syncCatalog() {
  const resp = await fetch("/api/pwa/catalog/dump/", {
    method: "GET",
    headers: { "Accept": "application/json" },
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!resp.ok) throw new Error(`CATALOG HTTP ${resp.status}`);
  const data = await resp.json();

  await clearStore("sites");
  await clearStore("systems");
  await putMany("sites", data.sites || []);
  await putMany("systems", data.systems || []);

  return { sites: data.sites?.length || 0, systems: data.systems?.length || 0 };
}

async function syncWorkorders() {
  const resp = await fetch("/api/pwa/workorders/dump/", {
    method: "GET",
    headers: { "Accept": "application/json" },
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!resp.ok) throw new Error(`WORKORDERS HTTP ${resp.status}`);
  const data = await resp.json();

  await clearStore("workorders");
  await putMany("workorders", data.workorders || []);

  return { workorders: data.workorders?.length || 0 };
}

let syncInProgress = false;

async function warmServiceReportPagesCache() {
  if (!("caches" in window)) return;

  const CACHE_NAME = "allsec-pwa-shell-v4";
  const cache = await caches.open(CACHE_NAME);

  const wos = await getAll("workorders");

  const serviceReportUrls = (wos || [])
    .filter(w => w?.service_report_id)
    .map(w => `/pwa/protokoly/serwis/${w.service_report_id}/`);

  const maintenanceUrls = (wos || [])
    .filter(w => w?.maintenance_protocol_id)
    .map(w => `/pwa/protokoly/konserwacja/${w.maintenance_protocol_id}/`);

  const workorderUrls = (wos || [])
    .map(w => `/pwa/zlecenia/${w.id}/`);

  const allUrls = [...serviceReportUrls, ...maintenanceUrls, ...workorderUrls];

  for (const url of allUrls) {
    try {
      const resp = await fetch(url, { credentials: "same-origin", cache: "no-store" });
      if (resp.ok) await cache.put(url, resp.clone());
    } catch (e) {
      console.warn("warm cache failed:", url, e);
    }
  }
}




async function doSyncAll({ silent = false } = {}) {
  if (syncInProgress) return;
  if (!navigator.onLine) {
    if (!silent) alert("Brak internetu — nie mogę zsynchronizować teraz.");
    return;
  }

  await processOutbox();

  syncInProgress = true;
  setBusy(true);

  try {
    const cat = await syncCatalog();
    const wo = await syncWorkorders();
    await warmServiceReportPagesCache(); // Cache'owanie raportów i zleceń

    const stamp = new Date().toLocaleString("pl-PL");
    await setMeta("last_sync", stamp);
    await setMeta("last_sync_ts", Date.now());

    if ($("lastSync")) $("lastSync").textContent = stamp;

    if (!silent) {
      alert(
        `SYNC OK ✅\nObiekty: ${cat.sites}\nSystemy: ${cat.systems}\nZlecenia: ${wo.workorders}`
      );
    }
  } catch (err) {
    console.error(err);
    if (!silent) alert("SYNC nieudany ❌\n" + (err?.message || err));
  } finally {
    setBusy(false);
    syncInProgress = false;
  }
}



export function initPwaHome() {
  updateOnlineUI();
  loadLastSync();

  const btn = $("syncBtn");
  if (btn) btn.addEventListener("click", () => doSyncAll({ silent: false }));

  // ping co 10s + po powrocie na kartę
  setInterval(updateOnlineUI, 10000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) updateOnlineUI();
  });

  // auto-sync: co 5 minut, tylko jak online i nie trwa sync
  setInterval(async () => {
    if (document.hidden) return;
    if (syncInProgress) return;

    const ok = await pingServer(800);
    if (!ok) return;

    const lastTs = await getMeta("last_sync_ts");
    const tooOld = !lastTs || (Date.now() - Number(lastTs)) > (5 * 60 * 1000);
    if (!tooOld) return;

    await doSyncAll({ silent: true });
  }, 60 * 1000); // sprawdzaj co minutę, sync max co 5 min

  initPwaWorkordersUi();

}

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

function getWorkorderIdFromPath() {
  const m = window.location.pathname.match(/^\/pwa\/zlecenia\/(\d+)\/?$/);
  return m ? Number(m[1]) : null;
}



function renderWorkorderCard(wo) {
  const siteLine = wo.site?.name
    ? `${wo.site.name}${(wo.site.street || wo.site.city) ? " - " : ""}${wo.site.street || ""}${wo.site.city ? " " + wo.site.city : ""}`
    : "Brak obiektu";

  const timeLine = `${wo.planned_time_from || ""}${wo.planned_time_to ? "–" + wo.planned_time_to : ""}`;

  const badges = [
    `<span class="badge text-bg-secondary">${wo.status_label || ""}</span>`,
    `<span class="badge text-bg-info">${wo.work_type_label || ""}</span>`,
    ...(wo.system_badges || []).map(lbl => `<span class="badge text-bg-light border text-dark">${lbl}</span>`),
    wo.system_badges_more ? `<span class="badge text-bg-light border text-dark">+${wo.system_badges_more}</span>` : ""
  ].join(" ");

  return `
    <a class="card pwa-card text-decoration-none text-dark" href="/pwa/zlecenia/${wo.id}/">
      <div class="card-body">
        <div class="d-flex justify-content-between align-items-start gap-2">
          <div>
            <div class="fw-semibold">${wo.title || ""}</div>
            <div class="small pwa-muted">${siteLine}</div>
          </div>
          <div class="small text-end pwa-muted">${timeLine}</div>
        </div>
        <div class="mt-2">${badges}</div>
      </div>
    </a>
  `;
}

async function renderWorkorderDetailOffline(woId) {
  const container = document.querySelector(".container-fluid.py-3");
  if (!container) return;

  const wo = await getByKey("workorders", woId);
  if (!wo) {
    container.innerHTML = `<div class="alert alert-warning border">Brak zlecenia w offline cache. Zrób SYNC.</div>`;
    return;
  }

  const siteId = wo.site?.id ?? wo.site_id ?? null;
  const site = siteId ? await getByKey("sites", siteId) : null;

  let systems = [];
  if (Array.isArray(wo.system_ids) && wo.system_ids.length) {
    const arr = [];
    for (const sid of wo.system_ids) {
      const s = await getByKey("systems", sid);
      if (s) arr.push(s);
    }
    systems = arr;
  }

  const siteLine = site
    ? `${esc(site.name)}${(site.street || site.city) ? " - " : ""}${esc(site.street || "")}${site.city ? " " + esc(site.city) : ""}`
    : (wo.site?.name ? esc(wo.site.name) : "Brak obiektu");

  const timeLine = `${wo.planned_time_from || ""}${wo.planned_time_to ? "–" + wo.planned_time_to : ""}`;

  container.innerHTML = `
    <div class="card pwa-card">
      <div class="card-body">
        <div class="d-flex align-items-center gap-2 mb-2">
          <button type="button"
                  class="btn btn-primary pwa-btn"
                  data-pwa-back
                  data-fallback="/pwa/zlecenia/">
            ← Powrót
          </button>
          <div class="small text-truncate">
            <div class="fw-semibold">
              Zlecenie ${esc(wo.work_type_label || "")}
              ${wo.number ? esc(wo.number) : ""}
              ${wo.planned_date ? " z " + esc(wo.planned_date.split("-").reverse().join(".")) : ""}
            </div>
          </div>
        </div>

        <div class="fw-semibold mb-1">${esc(wo.title || "")}</div>

        <div class="small pwa-muted mb-2">
          <div>Status: ${esc(wo.status_label || "")}</div>
          <div>Typ: ${esc(wo.work_type_label || "")}</div>
          ${wo.planned_date ? `<div>Termin: ${esc(wo.planned_date.split("-").reverse().join("."))}</div>` : ""}
          ${(wo.planned_time_from || wo.planned_time_to) ? `<div>Godzina: ${esc(timeLine)}</div>` : ""}
        </div>

        <hr>

        <div class="fw-semibold mb-1">Obiekt</div>
        <div class="mb-2">${siteLine}</div>

        ${site?.access_info ? `
          <div class="mt-2">
            <div class="fw-semibold small">Dostępy / informacje</div>
            <div class="small">${nl2br(site.access_info)}</div>
          </div>
        ` : ""}

        ${wo.description ? `
          <hr>
          <div class="fw-semibold mb-1">Opis</div>
          <div class="small">${nl2br(wo.description)}</div>
        ` : ""}

        <hr>
        <div class="fw-semibold mb-2">Systemy w zleceniu</div>

        ${
          systems.length
          ? systems.map(s => `
              <details class="card pwa-card mb-2">
                <summary class="card-body py-2" style="cursor:pointer;">
                  <span class="badge text-bg-info me-1">${esc(s.system_type || "")}</span>
                  <span class="fw-semibold">${esc((s.manufacturer || "") + " " + (s.model || "")).trim() || esc(s.name || "—")}</span>
                </summary>
                <div class="card-body small pt-0">
                  <div><span class="fw-semibold">Producent:</span> ${esc(s.manufacturer || "—")}</div>
                  <div><span class="fw-semibold">Model / typ:</span> ${esc(s.model || "—")}</div>
                  ${s.location_info ? `<div class="mt-2"><span class="fw-semibold">Lokalizacja:</span><br>${nl2br(s.location_info)}</div>` : ""}
                  ${s.access_data ? `<div class="mt-2"><span class="fw-semibold">Dostępy:</span><br>${nl2br(s.access_data)}</div>` : ""}
                  ${s.procedures ? `<div class="mt-2"><span class="fw-semibold">Procedury:</span><br>${nl2br(s.procedures)}</div>` : ""}
                  ${s.notes ? `<div class="mt-2"><span class="fw-semibold">Notatki:</span><br>${nl2br(s.notes)}</div>` : ""}
                </div>
              </details>
            `).join("")
          : `<div class="alert alert-light border mb-0">Brak systemów w offline cache. Zrób SYNC.</div>`
        }

        <div class="fixed-bottom bg-white border-top">
          <div class="container-fluid py-2">
            ${
              (wo.work_type === "SERVICE" && wo.service_report_id)
                ? `<a class="btn btn-primary w-100 pwa-btn"
                      href="/pwa/protokoly/serwis/${wo.service_report_id}/">
                      PROTOKÓŁ SERWISOWY
                   </a>`
                : (wo.work_type === "MAINTENANCE" && wo.maintenance_protocol_id)
                  ? `<a class="btn btn-primary w-100 pwa-btn"
                        href="/pwa/protokoly/konserwacja/${wo.maintenance_protocol_id}/">
                        PROTOKÓŁ KONSERWACJI
                     </a>`
                  : `<button class="btn btn-secondary w-100 pwa-btn" type="button" disabled>
                        PROTOKÓŁ (zrób SYNC online)
                     </button>`
            }
          </div>
        </div>


      </div>
    </div>
  `;
}


export async function initPwaWorkordersUi() {
  const woId = getWorkorderIdFromPath();

  const ok = await pingServer(800);
  if (!ok && woId) {
    await renderWorkorderDetailOffline(woId);
    return;
  }

  const nodes = document.querySelectorAll("[data-pwa-workorders]");
  if (!nodes.length) return;

  if (ok) return; // online: zostaw server-render

  const all = await getAll("workorders");

  for (const node of nodes) {
    const mode = node.dataset.mode || "all";
    let items = all.slice();

    if (mode === "today") {
      const todayIso = node.dataset.todayIso;
      if (todayIso) items = items.filter(w => w.planned_date === todayIso);
    }

    // sort: data + godzina
    items.sort((a, b) => (a.planned_time_from || "").localeCompare(b.planned_time_from || ""));

    node.innerHTML = items.length
      ? items.map(renderWorkorderCard).join("")
      : `<div class="alert alert-light border">Brak zleceń offline. Zrób SYNC.</div>`;
  }
}

function getCookie(name) {
  const v = `; ${document.cookie}`;
  const parts = v.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

async function processOutbox() {
  if (!navigator.onLine) return;

  const items = await listOutbox();
  if (!items.length) return;

  for (const item of items.sort((a, b) => (a.created_at || 0) - (b.created_at || 0))) {

    if (item.kind === "servicereport_save") {
      const payload = item.payload || {};
      if (payload.fields?.report_date) {
        payload.fields.report_date = normalizeDateToIso(payload.fields.report_date);
      }

      const resp = await fetch("/api/pwa/servicereport/save/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify(payload),
        credentials: "same-origin",
      });

      if (!resp.ok) break;
      await deleteOutbox(item.id);
      continue;
    }

    if (item.kind === "maintenanceprotocol_save") {
      const payload = item.payload || {};
      if (payload.fields?.date) {
        payload.fields.date = normalizeDateToIso(payload.fields.date);
      }

      const resp = await fetch("/api/pwa/maintenanceprotocol/save/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify(payload),
        credentials: "same-origin",
      });

      if (!resp.ok) break;
      await deleteOutbox(item.id);
      continue;
    }
  }
}


function serializeForm(form) {
  const fd = new FormData(form);
  const out = {};
  for (const [k, v] of fd.entries()) {
    if (k === "csrfmiddlewaretoken") continue;
    out[k] = v;
  }
  return out;
}

function normalizeDateToIso(value) {
  if (!value) return "";
  const s = String(value).trim();

  // już OK
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;

  // DD.MM.YYYY -> YYYY-MM-DD
  const m = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(s);
  if (m) {
    const dd = m[1].padStart(2, "0");
    const mm = m[2].padStart(2, "0");
    const yyyy = m[3];
    return `${yyyy}-${mm}-${dd}`;
  }

  return s;
}


function applyFieldsToForm(form, fields) {
  Object.entries(fields || {}).forEach(([name, value]) => {
    const el = form.elements.namedItem(name);
    if (!el) return;

    // RadioNodeList / HTMLCollection
    if (el instanceof RadioNodeList) {
      for (const opt of el) opt.checked = (opt.value === value);
      return;
    }

    if (el.type === "checkbox") {
      el.checked =
        value === true ||
        value === "on" ||
        value === "true" ||
        value === 1 ||
        value === "1";
      return;
    }

    if (el.type === "date") {
      el.value = normalizeDateToIso(value);
      return;
    }

    el.value = value ?? "";
  });
}


export function initPwaServiceReportForm() {
  const form = document.querySelector("form[data-pwa-sr-form]");
  if (!form) return;

  const srId = parseInt(form.dataset.srId || "", 10);
  const woId = parseInt(form.dataset.woId || "", 10);
  const backUrl = form.dataset.backUrl || "/pwa/";
  const backBtn = document.getElementById("srBackBtn");

  if (backBtn) {
    backBtn.addEventListener("click", () => {
      window.location.replace(backUrl);
    });
  }

  if (!srId) return;

  // =========================
  // 0) Przycisk "Dodaj wizytę" (dopisywanie bloku do work_performed)
  // =========================
  const visitBtn = document.getElementById("add-visit-entry");
  const visitTextarea = document.getElementById("id_work_performed");

  if (visitBtn && visitTextarea) {
    visitBtn.addEventListener("click", () => {
      let value = visitTextarea.value || "";

      // znajdź max numer "Wizyta X"
      const regex = /Wizyta\s+(\d+)/g;
      let maxVisit = 0;
      let match;
      while ((match = regex.exec(value)) !== null) {
        const num = parseInt(match[1], 10);
        if (!isNaN(num) && num > maxVisit) maxVisit = num;
      }
      const nextVisit = maxVisit + 1;

      // dd.mm.yyyy
      const today = new Date();
      const dd = String(today.getDate()).padStart(2, "0");
      const mm = String(today.getMonth() + 1).padStart(2, "0");
      const yyyy = today.getFullYear();
      const dateStr = `${dd}.${mm}.${yyyy}`;

      // technik z pola (jeśli jest)
      const techEl = document.getElementById("id_technicians");
      const tech = (techEl?.value || "").trim();

      const prefix = value.trim().length > 0 ? "\n\n" : "";
      const newBlock =
        `${prefix}Wizyta ${nextVisit} – ${dateStr}` +
        (tech ? ` – ${tech}` : "") +
        "\n– ";

      visitTextarea.value = value + newBlock;

      // kursor na koniec + trigger autosave
      visitTextarea.focus();
      visitTextarea.selectionStart = visitTextarea.selectionEnd = visitTextarea.value.length;
      visitTextarea.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  // =========================
  // 1) Restore draft (jeśli jest)
  // =========================
  getSrDraft(srId).then((draft) => {
    if (draft?.fields) applyFieldsToForm(form, draft.fields);
  });

  // =========================
  // 2) Autosave draft
  // =========================
  let t = null;
  const saveDraft = async () => {
    const fields = serializeForm(form);
    await putSrDraft(srId, { wo_id: woId, fields });
  };

  const onChange = () => {
    clearTimeout(t);
    t = setTimeout(saveDraft, 500);
  };

  form.addEventListener("input", onChange);
  form.addEventListener("change", onChange);

  // =========================
  // 3) SUBMIT: zawsze przechwytujemy (pingServer decyduje)
  // =========================
  let allowNativeSubmit = false;

  form.addEventListener("submit", async (e) => {
    if (allowNativeSubmit) return;

    e.preventDefault();

    // HTML5 validation
    if (typeof form.checkValidity === "function" && !form.checkValidity()) {
      if (typeof form.reportValidity === "function") form.reportValidity();
      return;
    }

    const ok = await pingServer(800);

    if (ok) {
      // ONLINE: normalny POST Django
      allowNativeSubmit = true;
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.submit();
      }
      return;
    }

    // OFFLINE: draft + outbox
    const fields = serializeForm(form);
    await putSrDraft(srId, { wo_id: woId, fields });
    await enqueueOutbox("servicereport_save", { sr_id: srId, wo_id: woId, fields });

    window.location.replace(backUrl);
  });
}


export function initPwaMaintenanceProtocolForm() {
  const form = document.querySelector("form[data-pwa-mp-form]");
  if (!form) return;

  const mpId = parseInt(form.dataset.mpId || "", 10);
  const woId = parseInt(form.dataset.woId || "", 10);
  const backUrl = form.dataset.backUrl || "/pwa/";
  const backBtn = document.getElementById("mpBackBtn");

  if (backBtn) {
    backBtn.addEventListener("click", () => {
      window.location.replace(backUrl);
    });
  }

  if (!mpId) return;

  // restore draft
  getMpDraft(mpId).then((draft) => {
    if (draft?.fields) applyFieldsToForm(form, draft.fields);
  });

  // autosave draft
  let t = null;
  const saveDraft = async () => {
    const fields = serializeForm(form);
    await putMpDraft(mpId, { wo_id: woId, fields });
  };

  const onChange = () => {
    clearTimeout(t);
    t = setTimeout(saveDraft, 500);
  };

  form.addEventListener("input", onChange);
  form.addEventListener("change", onChange);

  // submit intercept (pingServer decyduje)
  let allowNativeSubmit = false;

  form.addEventListener("submit", async (e) => {
    if (allowNativeSubmit) return;

    e.preventDefault();

    if (typeof form.checkValidity === "function" && !form.checkValidity()) {
      if (typeof form.reportValidity === "function") form.reportValidity();
      return;
    }

    const ok = await pingServer(800);

    if (ok) {
      allowNativeSubmit = true;
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.submit();
      }
      return;
    }

    // offline: draft + outbox
    const fields = serializeForm(form);
    await putMpDraft(mpId, { wo_id: woId, fields });
    await enqueueOutbox("maintenanceprotocol_save", { mp_id: mpId, wo_id: woId, fields });

    window.location.replace(backUrl);
  });
}

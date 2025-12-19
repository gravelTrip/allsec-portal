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
  const prev = await getAll("workorders");
  const prevMap = new Map((prev || []).map(w => [w.id, w]));

  const resp = await fetch("/api/pwa/workorders/dump/", {
    method: "GET",
    headers: { "Accept": "application/json" },
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!resp.ok) throw new Error(`WORKORDERS HTTP ${resp.status}`);
  const data = await resp.json();

  const incoming = data.workorders || [];

  // policz "nowe do realizacji" (IN_PROGRESS) względem poprzedniego stanu cache
  let newOnes = 0;
  for (const w of incoming) {
    if (w?.status_code !== "IN_PROGRESS") continue;
    const old = prevMap.get(w.id);
    if (!old || old.status_code !== "IN_PROGRESS") newOnes += 1;
  }

  const oldCount = Number(await getMeta("wo_notif_count") || 0);
  const nextCount = oldCount + newOnes;
  await setMeta("wo_notif_count", String(nextCount));

  await clearStore("workorders");
  await putMany("workorders", incoming);

  return { workorders: incoming.length || 0 };
}


let syncInProgress = false;

async function warmServiceReportPagesCache() {
  if (!("caches" in window)) return;

  const CACHE_NAME = "allsec-pwa-shell-v5";
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

  // ===== badge: licznik "nowe do realizacji" =====
  const updateWoBadge = async () => {
    const badge = $("woNotifBadge");
    if (!badge) return;

    const raw = await getMeta("wo_notif_count");
    const n = Number(raw || 0);

    if (n > 0) {
      badge.textContent = String(n);
      badge.style.display = "inline-block";
    } else {
      badge.textContent = "0";
      badge.style.display = "none";
    }
  };

  // pokaż badge od razu po wejściu na HOME
  updateWoBadge();

  const btn = $("syncBtn");
  if (btn) {
    btn.addEventListener("click", async () => {
      await doSyncAll({ silent: false });
      await updateWoBadge();
    });
  }

  // klik w "ZLECENIA" -> zeruj licznik i dopiero przejdź na listę
  const woBtn = $("workordersBtn");
  if (woBtn) {
    woBtn.addEventListener("click", async (e) => {
      const href = woBtn.getAttribute("href") || "/pwa/zlecenia/";
      e.preventDefault();

      await setMeta("wo_notif_count", "0");
      await updateWoBadge();

      window.location.href = href;
    });
  }

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
    await updateWoBadge();
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

  const stClass =
    wo.status_code === "IN_PROGRESS" ? "text-bg-success" :
    wo.status_code === "REALIZED" ? "text-bg-danger" :
    "text-bg-secondary";

  const wtCode =
    wo.work_type_code ||
    (wo.service_report_id ? "SERVICE" : null);

  const wtClass =
    wtCode === "MAINTENANCE" ? "text-bg-info" :
    wtCode === "SERVICE" ? "text-bg-primary" :
    "text-bg-secondary";

  const badges = [
    `<span class="badge ${stClass}">${esc(wo.status_label || "")}</span>`,
    `<span class="badge ${wtClass}">${esc(wo.work_type_label || "")}</span>`,
    ...(wo.system_badges || []).map(b => `<span class="badge text-bg-light border">${esc(b)}</span>`),
  ].filter(Boolean);


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

  const toggleLabel = (wo.status_code === "REALIZED") ? "PRZYWRÓĆ" : "ZREALIZUJ";
  const toggleBtnClass = (wo.status_code === "REALIZED") ? "btn-secondary" : "btn-success";
  const nextStatus = (wo.status_code === "REALIZED") ? "IN_PROGRESS" : "REALIZED";

  container.innerHTML = `
    <div class="card pwa-card">
      <div class="card-body">
        <div class="fw-semibold mb-1">${esc(wo.title || "")}</div>

        <div class="small pwa-muted mb-2">
          <div>Status: ${esc(wo.status_label || "")}</div>
          <div>Typ: ${esc(wo.work_type_label || "")}</div>
          ${wo.planned_date ? `<div>Termin: ${esc(wo.planned_date.split("-").reverse().join("."))}</div>` : ""}
          ${wo.planned_time_from || wo.planned_time_to ? `<div>Godzina: ${esc(wo.planned_time_from || "")}${wo.planned_time_to ? "– " + esc(wo.planned_time_to) : ""}</div>` : ""}
        </div>

        <hr>

        <div class="d-flex justify-content-between align-items-start gap-3">
          <div class="flex-grow-1">
            <div class="fw-semibold mb-1">Obiekt</div>
            ${
              site
                ? `<div class="mb-2">
                    ${esc(site.name || "")}<br>
                    <span class="small pwa-muted">${esc(site.street || "")}${site.city ? ", " + esc(site.city) : ""}</span>
                  </div>`
                : `<div class="alert alert-light border mb-2">Brak przypisanego obiektu.</div>`
            }
          </div>
        </div>

        ${wo.description ? `<hr><div class="fw-semibold mb-1">Opis</div><div class="small" style="white-space: pre-wrap;">${esc(wo.description)}</div>` : ""}

        <hr>
        <div class="fw-semibold mb-2">Systemy w zleceniu</div>
        ${
          systems.length
          ? systems.map(s => `
              <details class="mb-2">
                <summary><span class="badge text-bg-info me-1">${esc(s.system_type_label || s.system_type || "")}</span> <span class="fw-semibold">${esc((s.manufacturer || "") + " " + (s.model || "")).trim() || "—"}</span></summary>
                <div class="small mt-2">
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
            <div class="d-flex gap-2">
              <div class="flex-grow-1">
                ${
                  wo.service_report_id
                    ? `<a class="btn btn-primary w-100 pwa-btn" href="/pwa/protokoly/serwis/${wo.service_report_id}/">PROTOKÓŁ</a>`
                    : `<button class="btn btn-secondary w-100 pwa-btn" type="button" disabled>PROTOKÓŁ (zrób SYNC online)</button>`
                }
              </div>

              <div style="width: 160px;">
                <button
                  class="btn ${toggleBtnClass} w-100 pwa-btn"
                  type="button"
                  data-wo-status-toggle
                  data-wo-id="${wo.id}"
                  data-next-status="${nextStatus}"
                >${toggleLabel}</button>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  `;
}



export async function initPwaWorkordersUi() {
  const woId = getWorkorderIdFromPath();

  const ok = await pingServer(800);

  // jeśli jesteśmy na detailu zlecenia i offline -> podmień HTML offline
  if (!ok && woId) {
    await renderWorkorderDetailOffline(woId);
  }

  // zawsze podepnij obsługę przycisku ZREALIZUJ/PRZYWRÓĆ (online i offline)
  bindWorkorderStatusToggle();

  const nodes = document.querySelectorAll("[data-pwa-workorders]");
  if (!nodes.length) return;

  // online: zostaw server-render listy
  if (ok) return;

  const all = await getAll("workorders");

  for (const node of nodes) {
    const mode = node.dataset.mode || "all";
    let items = all.slice();

    // filtr PWA: tylko REALIZACJA + ZREALIZOWANE
    items = items.filter(w => ["IN_PROGRESS", "REALIZED"].includes(w.status_code));

    if (mode === "today") {
      const todayIso = node.dataset.todayIso;
      if (todayIso) items = items.filter(w => w.planned_date === todayIso);
    }

    items.sort((a, b) => (a.planned_time_from || "").localeCompare(b.planned_time_from || ""));

    node.innerHTML = items.length
      ? items.map(renderWorkorderCard).join("")
      : `<div class="alert alert-light border">Brak zleceń w offline cache. Zrób SYNC.</div>`;
  }
}


function getCookie(name) {
  const v = `; ${document.cookie}`;
  const parts = v.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

function getCsrfToken() {
  return getCookie("csrftoken") || "";
}

async function processOutbox() {
  if (!navigator.onLine) return;

  const items = await listOutbox();
  if (!items.length) return;

  for (const item of items.sort((a, b) => (a.created_at || 0) - (b.created_at || 0))) {

    // =========================
    // 1) ServiceReport save
    // =========================
    if (item.kind === "servicereport_save") {
      const payload = item.payload || {};

      if (payload.fields?.report_date) {
        payload.fields.report_date = normalizeDateToIso(payload.fields.report_date);
      }

      const resp = await fetch("/api/pwa/servicereport/save/", {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify(payload),
        credentials: "same-origin",
      });

      if (!resp.ok) break;

      await deleteOutbox(item.id);
      continue;
    }

    // =========================
    // 2) MaintenanceProtocol save  ✅ NOWE
    // =========================
    if (item.kind === "maintenanceprotocol_save") {
      const payload = item.payload || {};

      // normalizuj potencjalne pola dat
      if (payload.fields) {
        for (const k of Object.keys(payload.fields)) {
          if (k === "date" || k.endsWith("_date")) {
            payload.fields[k] = normalizeDateToIso(payload.fields[k]);
          }
        }
      }

      const resp = await fetch("/api/pwa/maintenanceprotocol/save/", {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify(payload),
        credentials: "same-origin",
      });

      if (!resp.ok) break;

      await deleteOutbox(item.id);
      continue;
    }

    // =========================
    // 3) Workorder status set
    // =========================
    if (item.kind === "workorder_status_set") {
      const woId = item.payload?.workorder_id;
      const status = item.payload?.status;

      const resp = await fetch(`/api/pwa/workorders/${woId}/set-status/`, {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({ status }),
        credentials: "same-origin",
      });

      if (!resp.ok) break;

      try {
        const data = await resp.json();
        const wo = await getByKey("workorders", data.id);
        if (wo) {
          wo.status_code = data.status_code;
          wo.status_label = data.status_label;
          await putMany("workorders", [wo]);
        }
      } catch (_) {}

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

function bindWorkorderStatusToggle() {
  const applyOffline = async (woId, nextStatus) => {
    // 1) outbox – to MUSI się udać (inaczej nie mamy co syncować)
    await enqueueOutbox("workorder_status_set", { workorder_id: woId, status: nextStatus });

    // 2) lokalna aktualizacja – best-effort (nie może wywalać całości)
    try {
      const wo = await getByKey("workorders", woId);
      if (wo) {
        wo.status_code = nextStatus;
        wo.status_label = (nextStatus === "REALIZED") ? "Zrealizowane" : "Realizacja";
        await putMany("workorders", [wo]);
      }
    } catch (e) {
      console.warn("Offline: nie udało się zaktualizować IDB workorders, ale outbox zapisany.", e);
    }
  };

  const paintButton = (btn, statusNow) => {
    const isRealized = (statusNow === "REALIZED");

    btn.textContent = isRealized ? "PRZYWRÓĆ" : "ZREALIZUJ";
    btn.dataset.nextStatus = isRealized ? "IN_PROGRESS" : "REALIZED";

    btn.classList.remove("btn-success", "btn-secondary");
    btn.classList.add(isRealized ? "btn-secondary" : "btn-success");
  };

  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-wo-status-toggle]");
    if (!btn) return;

    e.preventDefault();

    const woId = Number(btn.dataset.woId);
    const nextStatus = btn.dataset.nextStatus;

    btn.disabled = true;

    try {
      const ok = await pingServer(800);

      if (ok) {
        try {
          const resp = await fetch(`/api/pwa/workorders/${woId}/set-status/`, {
            method: "POST",
            headers: {
              "Accept": "application/json",
              "Content-Type": "application/json",
              "X-CSRFToken": getCsrfToken(),
            },
            body: JSON.stringify({ status: nextStatus }),
            credentials: "same-origin",
          });

          if (!resp.ok) throw new Error("HTTP " + resp.status);

          const data = await resp.json();

          try {
            const wo = await getByKey("workorders", woId);
            if (wo) {
              wo.status_code = data.status_code;
              wo.status_label = data.status_label;
              await putMany("workorders", [wo]);
            }
          } catch (e) {
            console.warn("Online: status zmieniony na serwerze, ale nie udało się zaktualizować IDB.", e);
          }

          paintButton(btn, data.status_code);
          return;

        } catch (errOnline) {
          console.warn("Online request padł — przechodzę w OFFLINE fallback.", errOnline);
          await applyOffline(woId, nextStatus);
          paintButton(btn, nextStatus);
          return;
        }
      }

      // OFFLINE (ping nie przeszedł)
      await applyOffline(woId, nextStatus);
      paintButton(btn, nextStatus);

    } catch (err) {
      console.error("Toggle status FAILED:", err);
      alert("Nie udało się zmienić statusu. Spróbuj ponownie.");
    } finally {
      btn.disabled = false;
    }
  }, { passive: false });
}



async function updateWoNotifBadge() {
  const badge = document.getElementById("woNotifBadge");
  if (!badge) return;

  // jeśli masz IDB z workorders: liczymy ile jest w bazie lokalnej
  // i pokazujemy po prostu "ile jest do roboty" (Realizacja + Zrealizowane)
  try {
    const all = await getAll("workorders");
    const count = (all || []).filter(w => w && (w.status === "IN_PROGRESS" || w.status === "REALIZED")).length;

    if (count > 0) {
      badge.textContent = String(count);
      badge.style.display = "inline-block";
    } else {
      badge.style.display = "none";
    }
  } catch (e) {
    badge.style.display = "none";
  }
}

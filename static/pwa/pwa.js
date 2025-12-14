// core/static/pwa/pwa.js
import { clearStore, putMany, setMeta, getMeta } from "./idb.js";

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

async function doSyncCatalog() {
  if (!navigator.onLine) {
    alert("Brak internetu — nie mogę zsynchronizować teraz.");
    return;
  }

  setBusy(true);
  try {
    const resp = await fetch("/api/pwa/catalog/dump/", {
      method: "GET",
      headers: { "Accept": "application/json" },
      credentials: "same-origin",
      cache: "no-store",
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

    const data = await resp.json();

    await clearStore("sites");
    await clearStore("systems");
    await putMany("sites", data.sites || []);
    await putMany("systems", data.systems || []);

    const stamp = new Date().toLocaleString("pl-PL");
    await setMeta("last_sync", stamp);

    if ($("lastSync")) $("lastSync").textContent = stamp;

    alert(`SYNC OK ✅\nObiekty: ${data.sites?.length || 0}\nSystemy: ${data.systems?.length || 0}`);
  } catch (err) {
    console.error(err);
    alert("SYNC nieudany ❌\n" + (err?.message || err));
  } finally {
    setBusy(false);
  }
}

export function initPwaHome() {
  updateOnlineUI();
  loadLastSync();

  const btn = $("syncBtn");
  if (btn) btn.addEventListener("click", doSyncCatalog);

  // ping co 10s + po powrocie na kartę
  setInterval(updateOnlineUI, 10000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) updateOnlineUI();
  });
}

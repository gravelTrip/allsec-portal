// core/static/pwa/pwa.js
import { clearStore, putMany, setMeta, getMeta } from "./idb.js";

function $(id) {
  return document.getElementById(id);
}

function updateOnlineUI() {
  const online = navigator.onLine;
  if ($("netDot")) $("netDot").textContent = online ? "🟢" : "🔴";
  if ($("netText")) $("netText").textContent = online ? "online" : "offline";
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

  window.addEventListener("online", updateOnlineUI);
  window.addEventListener("offline", updateOnlineUI);

  const btn = $("syncBtn");
  if (btn) btn.addEventListener("click", doSyncCatalog);

  // bezpiecznik (czasem eventy online/offline w DevTools bywają kapryśne)
  setInterval(updateOnlineUI, 1000);
}

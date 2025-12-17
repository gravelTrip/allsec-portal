// core/static/pwa/idb.js
// Minimalny helper IndexedDB bez bibliotek zewnętrznych.

const DB_NAME = "allsec_pwa";
const DB_VERSION = 4;

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);

    req.onupgradeneeded = (event) => {
      const db = event.target.result;
      const oldVersion = event.oldVersion || 0;

      if (!db.objectStoreNames.contains("sites")) {
        db.createObjectStore("sites", { keyPath: "id" });
      }

      if (!db.objectStoreNames.contains("systems")) {
        const store = db.createObjectStore("systems", { keyPath: "id" });
        store.createIndex("by_site_id", "site_id", { unique: false });
      }

      if (!db.objectStoreNames.contains("meta")) {
        db.createObjectStore("meta", { keyPath: "key" });
      }

      if (!db.objectStoreNames.contains("workorders")) {
        db.createObjectStore("workorders", { keyPath: "id" });
      }

      if (oldVersion < 3) {
        if (!db.objectStoreNames.contains("sr_drafts")) {
          db.createObjectStore("sr_drafts", { keyPath: "sr_id" });
        }
        if (!db.objectStoreNames.contains("outbox")) {
          const outbox = db.createObjectStore("outbox", { keyPath: "id", autoIncrement: true });
          outbox.createIndex("kind", "kind", { unique: false });
          outbox.createIndex("created_at", "created_at", { unique: false });
        }
      }

      if (oldVersion < 4) {
        if (!db.objectStoreNames.contains("mp_drafts")) {
          db.createObjectStore("mp_drafts", { keyPath: "mp_id" });
        }
      }
    };

    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}


function txDone(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

export async function putMany(storeName, items) {
  const db = await openDb();
  const tx = db.transaction([storeName], "readwrite");
  const store = tx.objectStore(storeName);
  for (const item of items) store.put(item);
  await txDone(tx);
  db.close();
}

export async function clearStore(storeName) {
  const db = await openDb();
  const tx = db.transaction([storeName], "readwrite");
  tx.objectStore(storeName).clear();
  await txDone(tx);
  db.close();
}

export async function setMeta(key, value) {
  const db = await openDb();
  const tx = db.transaction(["meta"], "readwrite");
  tx.objectStore("meta").put({ key, value });
  await txDone(tx);
  db.close();
}

export async function getMeta(key) {
  const db = await openDb();
  const tx = db.transaction(["meta"], "readonly");
  const req = tx.objectStore("meta").get(key);
  const result = await new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  db.close();
  return result ? result.value : null;
}

export async function getAll(storeName) {
  const db = await openDb();
  const tx = db.transaction([storeName], "readonly");
  const store = tx.objectStore(storeName);

  const req = store.getAll();
  const result = await new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });

  db.close();
  return result;
}

export async function getByKey(storeName, key) {
  const db = await openDb();
  const tx = db.transaction([storeName], "readonly");
  const store = tx.objectStore(storeName);

  const req = store.get(key);
  const result = await new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });

  db.close();
  return result;
}

export async function getAllByIndex(storeName, indexName, key) {
  const db = await openDb();
  const tx = db.transaction([storeName], "readonly");
  const store = tx.objectStore(storeName);
  const idx = store.index(indexName);

  const req = idx.getAll(key);
  const result = await new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });

  db.close();
  return result;
}

export async function putSrDraft(sr_id, payload) {
  const db = await openDb();
  const tx = db.transaction(["sr_drafts"], "readwrite");
  tx.objectStore("sr_drafts").put({ sr_id, ...payload, saved_at: Date.now() });
  await txDone(tx);
  db.close();
}

export async function getSrDraft(sr_id) {
  const db = await openDb();
  const tx = db.transaction(["sr_drafts"], "readonly");
  const req = tx.objectStore("sr_drafts").get(sr_id);
  const result = await new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
  db.close();
  return result;
}

export async function enqueueOutbox(kind, payload) {
  const db = await openDb();
  const tx = db.transaction(["outbox"], "readwrite");
  tx.objectStore("outbox").add({ kind, payload, created_at: Date.now() });
  await txDone(tx);
  db.close();
}

export async function listOutbox() {
  const db = await openDb();
  const tx = db.transaction(["outbox"], "readonly");
  const req = tx.objectStore("outbox").getAll();
  const result = await new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
  db.close();
  return result;
}

export async function deleteOutbox(id) {
  const db = await openDb();
  const tx = db.transaction(["outbox"], "readwrite");
  tx.objectStore("outbox").delete(id);
  await txDone(tx);
  db.close();
}

export async function putMpDraft(mp_id, payload) {
  const db = await openDb();
  const tx = db.transaction(["mp_drafts"], "readwrite");
  tx.objectStore("mp_drafts").put({ mp_id, ...payload, saved_at: Date.now() });
  await txDone(tx);
  db.close();
}

export async function getMpDraft(mp_id) {
  const db = await openDb();
  const tx = db.transaction(["mp_drafts"], "readonly");
  const req = tx.objectStore("mp_drafts").get(mp_id);
  const result = await new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
  db.close();
  return result;
}

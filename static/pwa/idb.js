// core/static/pwa/idb.js
// Minimalny helper IndexedDB bez bibliotek zewnętrznych.

const DB_NAME = "allsec_pwa";
const DB_VERSION = 2;

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);

    req.onupgradeneeded = (event) => {
      const db = req.result;

      // sites: klucz id
      if (!db.objectStoreNames.contains("sites")) {
        db.createObjectStore("sites", { keyPath: "id" });
      }

      // systems: klucz id + index po site_id do szybkiego filtrowania
      if (!db.objectStoreNames.contains("systems")) {
        const store = db.createObjectStore("systems", { keyPath: "id" });
        store.createIndex("by_site_id", "site_id", { unique: false });
      }

      // meta: na ustawienia / last_sync itp.
      if (!db.objectStoreNames.contains("meta")) {
        db.createObjectStore("meta", { keyPath: "key" });
      }

      // workorders: klucz id
      if (!db.objectStoreNames.contains("workorders")) {
        db.createObjectStore("workorders", { keyPath: "id" });
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

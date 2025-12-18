// core/static/pwa/sw.js
// SW tylko dla "app shell": PWA strony + statyki.
// Dane są w IndexedDB, więc NIE cache'ujemy /api/.

const CACHE_NAME = "allsec-pwa-shell-v5";

const SHELL_URLS = [
  "/pwa/",
  "/pwa/obiekty/",
  "/static/css/main.css",
  "/static/pwa/pwa.js",
  "/static/pwa/idb.js",
  "/static/pwa/objects.js",
  "/pwa/zlecenia/",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.map((k) => (k === CACHE_NAME ? null : caches.delete(k))))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  if (url.origin !== self.location.origin) return;
  if (req.method !== "GET") return;

  // NIE cache'ujemy API
  if (url.pathname.startsWith("/api/")) return;

  // 1) NAWIGACJA (HTML): offline ma zwrócić shell
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          return resp;
        })
        .catch(async () => {
          // offline: najpierw spróbuj stronę po pathname (ignorujemy querystring)
          const cachedExact = await caches.match(url.pathname, { ignoreSearch: true });
          if (cachedExact) return cachedExact;
          // jeśli to szczegóły zlecenia (/pwa/zlecenia/<id>/), a nie mamy exact w cache,
          // oddaj shell listy zleceń, który ma JS do renderu offline
          if (url.pathname.startsWith("/pwa/zlecenia/")) {
            const cachedList = await caches.match("/pwa/zlecenia/", { ignoreSearch: true });
            if (cachedList) return cachedList;
          }

          // fallback na /pwa/
          if (url.pathname.startsWith("/pwa/protokoly/serwis/")) {
            const cachedList = await caches.match("/pwa/zlecenia/", { ignoreSearch: true });
            if (cachedList) return cachedList;
          }

          return caches.match("/pwa/", { ignoreSearch: true });
        })
    );
    return;
  }

  // 2) STATYKI: cache-first (ignorujemy querystring)
  event.respondWith(
    caches.match(req, { ignoreSearch: true }).then((cached) => {
      if (cached) return cached;

      return fetch(req)
        .then((resp) => {
          if (url.pathname.startsWith("/static/") || url.pathname.startsWith("/pwa/")) {
            const copy = resp.clone();
            try {
              if (resp && resp.ok) {
                const copy = resp.clone();
                caches.open(CACHE_NAME)
                  .then(cache => cache.put(req, copy))
                  .catch(() => {});
              }
            } catch (e) {
              // ignorujemy błąd klonowania
            }
            return resp;
          }
          return resp;
        })
        .catch(async () => {
          // jeśli totalnie brak — oddaj cokolwiek z cache (albo nic)
          return cached || (await caches.match("/pwa/", { ignoreSearch: true }));
        });
    })
  );
});

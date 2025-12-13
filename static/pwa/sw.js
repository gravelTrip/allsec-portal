// core/static/pwa/sw.js
// SW dla "app shell": tylko PWA strony + statyki.
// Dane (catalog) są w IndexedDB, więc NIE cache'ujemy /api/.

const CACHE_NAME = "allsec-pwa-shell-v1";

const SHELL_URLS = [
  "/pwa/",
  "/pwa/obiekty/",
  "/static/css/main.css",
  "/static/pwa/pwa.js",
  "/static/pwa/idb.js",
  "/static/pwa/objects.js",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((k) => (k === CACHE_NAME ? null : caches.delete(k)))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // tylko nasza domena
  if (url.origin !== self.location.origin) return;

  // NIE cache'ujemy API
  if (url.pathname.startsWith("/api/")) return;

  // tylko GET
  if (req.method !== "GET") return;

  // "Cache-first" dla shell + statyk: offline ma działać po refresh
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req)
        .then((resp) => {
          // dorzucamy do cache tylko statyki i /pwa/
          if (
            url.pathname.startsWith("/static/") ||
            url.pathname.startsWith("/pwa/")
          ) {
            const copy = resp.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          }
          return resp;
        })
        .catch(() => {
          // jeśli nie ma w cache i offline -> fallback na /pwa/
          return caches.match("/pwa/");
        });
    })
  );
});

/* Service worker: cache-first for static assets, network-first for
 * HTML pages and API responses. Keeps the app shell usable offline
 * (iOS home-screen PWA requirement) without serving stale data.
 */

const STATIC_CACHE = "ws-static-v2";
const RUNTIME_CACHE = "ws-runtime-v2";

const STATIC_ASSETS = [
  "/static/styles.css",
  "/static/app.js",
  "/static/analysis.js",
  "/static/new-entry.js",
  "/static/vendor/chart.umd.min.js",
  "/static/icons/icon.svg",
  "/static/icons/apple-touch-icon.png",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_ASSETS)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((n) => ![STATIC_CACHE, RUNTIME_CACHE].includes(n))
          .map((n) => caches.delete(n)),
      ),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Static assets under /static/ — cache-first.
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then((cached) =>
        cached ||
        fetch(request).then((resp) => {
          const clone = resp.clone();
          caches.open(STATIC_CACHE).then((c) => c.put(request, clone));
          return resp;
        }),
      ),
    );
    return;
  }

  // API: network-first, fall back to cache if offline.
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(request)
        .then((resp) => {
          const clone = resp.clone();
          caches.open(RUNTIME_CACHE).then((c) => c.put(request, clone));
          return resp;
        })
        .catch(() => caches.match(request)),
    );
    return;
  }

  // HTML pages: network-first, fall back to cached shell.
  event.respondWith(
    fetch(request)
      .then((resp) => {
        const clone = resp.clone();
        caches.open(RUNTIME_CACHE).then((c) => c.put(request, clone));
        return resp;
      })
      .catch(() => caches.match(request).then((cached) => cached || caches.match("/"))),
  );
});

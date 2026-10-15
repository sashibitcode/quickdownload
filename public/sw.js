// QuickDownload PWA Service Worker (v1)
const CACHE_NAME = "quickdownload-pwa-v1";
const STATIC_ASSETS = [
  "/",
  "/favicon.svg",
  "/manifest.webmanifest",
  "/pwa-192x192.png",
  "/pwa-512x512.png",
  "/apple-touch-icon.png",
];

// Install: pre-cache core static shell
self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn("[SW] Cache addAll warning:", err);
      });
    })
  );
});

// Activate: clean up obsolete caches and claim clients immediately
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: Network-first for dynamic navigation, stale-while-revalidate for static assets, NEVER cache API
self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // 1. NEVER intercept or cache POST/PUT/DELETE requests
  if (req.method !== "GET") {
    return;
  }

  // 2. NEVER cache backend download or API endpoints
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/download") ||
    url.hostname.includes("onrender.com") ||
    url.hostname.includes("googlevideo.com") ||
    url.hostname.includes("cdninstagram.com")
  ) {
    return;
  }

  // 3. For navigation (HTML page load), use Network-First with Cache fallback
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((response) => {
          if (response && response.status === 200) {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          }
          return response;
        })
        .catch(async () => {
          const cached = await caches.match("/");
          return cached || new Response("QuickDownload offline. Please reconnect.", {
            headers: { "Content-Type": "text/html" }
          });
        })
    );
    return;
  }

  // 4. For static assets (JS, CSS, fonts, images), use Stale-While-Revalidate
  event.respondWith(
    caches.match(req).then((cached) => {
      const fetchPromise = fetch(req)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const copy = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, copy));
          }
          return networkResponse;
        })
        .catch(() => cached);

      return cached || fetchPromise;
    })
  );
});

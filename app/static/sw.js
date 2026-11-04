// Minimal service worker: makes the site installable (and a share target). Network first, cache as offline fallback.
const CACHE = "pantry-v4";
const STATIC = ["/static/style.css", "/static/app.js", "/static/pixel.js", "/static/fonts/pixelify.woff2", "/static/fonts/jersey15.woff2", "/static/icon-192.png"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  // network first, cache as the offline fallback (so style and script updates land on the phone right away)
  e.respondWith(fetch(e.request).then(res => { const copy = res.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); return res; }).catch(() => caches.match(e.request)));
});

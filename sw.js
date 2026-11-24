/* Сервіс-воркер: дозволяє встановити сайт як застосунок і показує останні завантажені новини без мережі.
   Стратегія: спершу мережа (завжди свіжі дані), кеш лише якщо мережі немає. */
const CACHE = "dobirka-v1";
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const r = e.request;
  if (r.method !== "GET" || new URL(r.url).origin !== location.origin) return;
  e.respondWith(
    fetch(r).then(res => {
      if (res.ok) { const c = res.clone(); caches.open(CACHE).then(ca => ca.put(r, c)); }
      return res;
    }).catch(() => caches.match(r).then(m => m || caches.match("/")))
  );
});

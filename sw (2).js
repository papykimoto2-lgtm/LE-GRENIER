// Le Grenier CI — Service Worker
// Rôle : rendre le site installable (PWA) + secours hors-ligne minimal.
// Ne met PAS en cache les appels Supabase (données toujours fraîches en ligne).
const CACHE_NAME = 'legrenier-shell-v1';
const APP_SHELL = [
  '/',
  '/icon-192.png',
  '/icon-512.png',
];

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL).catch(() => {}))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Stratégie : réseau d'abord (site dynamique/Supabase), secours cache si hors-ligne
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  // Ne jamais intercepter les appels vers l'API Supabase (toujours en ligne)
  if (event.request.url.includes('supabase.co')) return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)).catch(() => {});
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match('/')))
  );
});

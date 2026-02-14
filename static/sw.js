const CACHE_NAME = "sns-multi-post-v1";
const urlsToCache = [
  "/",
  "/static/manifest.json",
  "https://cdn.tailwindcss.com",
  "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css",
];

// インストールイベント - リソースをキャッシュ
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log("Opened cache text");
      return cache.addAll(urlsToCache);
    }),
  );
  self.skipWaiting();
});

// フェッチイベント - キャッシュから提供、なければネットワークから取得
self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      // キャッシュヒット - レスポンスを返す
      if (response) {
        return response;
      }
      return fetch(event.request);
    }),
  );
});

// アクティベートイベント - 古いキャッシュをクリーンアップ
self.addEventListener("activate", (event) => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        }),
      );
    }),
  );
  self.clients.claim();
});

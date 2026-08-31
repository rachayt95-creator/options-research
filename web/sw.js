const VERSION = "v8";
const CACHE = `optiradar-${VERSION}`;

const SHELL = [
  "./", "./index.html", "./styles.css", "./app.js", "./manifest.json",
  "./icons/icon-192.png", "./icons/icon-512.png", "./icons/apple-touch-icon.png",
];

// קבצים שמשתנים בכל פריסה. הם נשלפים מהרשת קודם, אחרת המשתמש מריץ
// לנצח את הקוד הישן בזמן שהחדש רק "מתעדכן ברקע" לפעם הבאה שלא מגיעה.
const VOLATILE = ["/", "/index.html", "/app.js", "/styles.css"];
const NET_TIMEOUT = 2500;   // תקרה כדי שהתעוררות השרת לא תתקע את הפתיחה

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

/** רשת קודם, אך לא יותר מ-NET_TIMEOUT. נופל למטמון, ומעדכן אותו ברקע. */
function freshFirst(request, key) {
  const cacheKey = key || request;
  return caches.match(cacheKey).then((cached) => {
    const network = fetch(request).then((res) => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(cacheKey, copy));
      }
      return res;
    });
    if (!cached) return network.catch(() => caches.match("./index.html"));
    return Promise.race([
      network.catch(() => cached),
      new Promise((done) => setTimeout(() => done(cached), NET_TIMEOUT)),
    ]);
  });
}

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // נתוני מסחר חייבים להיות טריים — לעולם לא מהמטמון
  if (e.request.method !== "GET" || url.pathname.includes("/api/")) return;
  if (url.origin !== location.origin) return;

  if (e.request.mode === "navigate") {
    e.respondWith(freshFirst(e.request, "./index.html"));
    return;
  }

  if (VOLATILE.some((p) => url.pathname === p || url.pathname.endsWith(p))) {
    e.respondWith(freshFirst(e.request));
    return;
  }

  // אייקונים ו-manifest: יציבים, מותר להגיש מהמטמון ולרענן ברקע
  e.respondWith(
    caches.match(e.request).then((hit) => {
      const network = fetch(e.request)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(e.request, copy));
          }
          return res;
        })
        .catch(() => hit);
      return hit || network;
    })
  );
});

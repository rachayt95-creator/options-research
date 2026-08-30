// גרסה זו נדרשת כדי לפנות מטמונים ישנים. יש להעלות אותה כשמשתנה מעטפת האפליקציה.
const VERSION = "v5";
const CACHE = `optiradar-${VERSION}`;

const SHELL = [
  "./", "./index.html", "./styles.css", "./app.js", "./manifest.json",
  "./icons/icon-192.png", "./icons/icon-512.png", "./icons/apple-touch-icon.png",
];

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

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // נתוני מסחר חייבים להיות טריים — לעולם לא מהמטמון
  if (e.request.method !== "GET" || url.pathname.includes("/api/")) return;
  if (url.origin !== location.origin) return;

  // ניווט: רשת קודם, אבל עם תקרת המתנה.
  //
  // השרת בשכבה החינמית נרדם, וההתעוררות אורכת עד דקה. בלי התקרה
  // המשתמש היה בוהה בעמוד ההמתנה של הספק. עכשיו: אם הרשת לא ענתה
  // תוך 2.5 שניות מגישים את המעטפת השמורה, האפליקציה נפתחת מיד,
  // והתשובה מהרשת ממשיכה להתעדכן במטמון ברקע לטעינה הבאה.
  if (e.request.mode === "navigate") {
    e.respondWith(
      caches.match("./index.html").then((cached) => {
        const network = fetch(e.request).then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put("./index.html", copy));
          return res;
        });
        if (!cached) return network.catch(() => caches.match("./"));
        return Promise.race([
          network.catch(() => cached),
          new Promise((done) => setTimeout(() => done(cached), 2500)),
        ]);
      })
    );
    return;
  }

  // נכסים: מגישים מהמטמון לתגובה מיידית, ומרעננים ברקע לפעם הבאה
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

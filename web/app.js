"use strict";

const $ = (id) => document.getElementById(id);
const el = { form:$("form"), symbol:$("symbol"), target:$("target"), go:$("go"),
             error:$("error"), results:$("results"), news:$("news"),
             levels:$("levels"), chain:$("chain"), chainMeta:$("chain-meta"),
             aiBody:$("ai-body"), netdot:$("netdot"),
             symPanel:$("symbol-panel"), symList:$("symbol-list"),
             dateBtn:$("date-btn"), dateText:$("date-text"), dateDte:$("date-dte"),
             cal:$("cal"), calTitle:$("cal-title"), calGrid:$("cal-grid"),
             earnAlert:$("earnings-alert"), earnText:$("earnings-text"),
             history:$("history"), histChips:$("history-chips"), tv:$("tv-chart") };

let chainData = { calls: [], puts: [] };
let spot = null;

// ------------------------------------------------------------------ עזרים

const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));

const num = (v, d = 2) =>
  v === null || v === undefined || Number.isNaN(v)
    ? "—"
    : Number(v).toLocaleString("en-US", { minimumFractionDigits:d, maximumFractionDigits:d });

function showError(msg, warn = false) {
  el.error.textContent = msg;
  el.error.className = warn ? "alert warn" : "alert";
  el.error.hidden = false;
}

/** רנדור Markdown מצומצם — רק מה ש-Gemini מחזיר. מסונן מראש מ-HTML. */
function renderMarkdown(md) {
  const out = [];
  let inList = false;
  for (const raw of esc(md).split("\n")) {
    const line = raw.trim();
    if (!line) { if (inList) { out.push("</ul>"); inList = false; } continue; }

    const bold = (t) => t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

    if (/^#{2,3}\s+/.test(line)) {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<h3>${bold(line.replace(/^#{2,3}\s+/, ""))}</h3>`);
    } else if (/^[-*]\s+/.test(line)) {
      if (!inList) { out.push("<ul>"); inList = true; }
      out.push(`<li>${bold(line.replace(/^[-*]\s+/, ""))}</li>`);
    } else {
      if (inList) { out.push("</ul>"); inList = false; }
      out.push(`<p>${bold(line)}</p>`);
    }
  }
  if (inList) out.push("</ul>");
  return out.join("");
}

const skeleton = (n) =>
  Array.from({ length:n }, (_, i) =>
    `<div class="skeleton sk-line ${["w80","w60","w40"][i % 3]}"></div>`).join("");

// ------------------------------------------------------------------ רנדור

function renderHero(s) {
  spot = s.price;
  $("h-symbol").textContent = s.symbol;
  $("h-name").textContent = s.name || "";
  $("h-price").textContent = num(s.price);

  const chip = $("h-change");
  if (s.change_pct === null || s.change_pct === undefined) {
    chip.textContent = "—"; chip.className = "chip";
  } else {
    const up = s.change_pct >= 0;
    chip.textContent = `${up ? "▲" : "▼"} ${num(Math.abs(s.change_pct))}%`;
    chip.className = `chip ${up ? "up" : "down"}`;
  }
  $("h-meta").textContent = `${s.currency || ""} · עדכון אחרון ${s.last_update || "—"}`;
}

function renderLevels(rows) {
  const maxDist = Math.max(...rows.map((r) => Math.abs(r["מרחק מהמחיר %"] ?? 0)), 1);
  el.levels.innerHTML = rows.map((r) => {
    const name = r["רמה"] ?? "";
    const dist = r["מרחק מהמחיר %"];
    const isNow = name.includes("נוכחי");
    const up = (dist ?? 0) >= 0;
    const width = Math.abs(dist ?? 0) / maxDist * 100;
    return `<li class="${isNow ? "now" : ""}">
      <div class="row">
        <span class="name">${esc(name)}</span>
        <span>
          <span class="val">${num(r["מחיר"])}</span>
          ${isNow || dist === null || dist === undefined ? "" :
            `<span class="dist ${up ? "up-c" : "down-c"}"> ${up ? "+" : ""}${num(dist)}%</span>`}
        </span>
      </div>
      ${isNow ? "" : `<div class="bar"><span style="width:${width}%;background:${
        up ? "var(--green)" : "var(--red)"}"></span></div>`}
    </li>`;
  }).join("");
}

function renderNews(items) {
  el.news.innerHTML = items.length
    ? items.map((n) => {
        const link = n["קישור"];
        const inner = `<div class="t">${esc(n["כותרת"])}</div>
                       <div class="m">${esc(n["מקור"])} · ${esc(n["פורסם"])}</div>`;
        return `<li>${link
          ? `<a href="${esc(link)}" target="_blank" rel="noopener">${inner}</a>`
          : `<div style="padding:.75rem 0">${inner}</div>`}</li>`;
      }).join("")
    : `<li><p class="muted">לא נמצאו חדשות עדכניות.</p></li>`;
}

function renderChain(side) {
  const rows = chainData[side] || [];
  const head = el.chain.tHead, body = el.chain.tBodies[0];
  if (!rows.length) {
    head.innerHTML = ""; body.innerHTML =
      `<tr><td class="muted" style="text-align:center">אין נתונים</td></tr>`;
    return;
  }
  const cols = Object.keys(rows[0]);
  head.innerHTML = `<tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>`;

  // הדגשת הסטרייק הקרוב ביותר למחיר
  let atm = -1, best = Infinity;
  rows.forEach((r, i) => {
    const d = Math.abs((r["סטרייק"] ?? 0) - (spot ?? 0));
    if (d < best) { best = d; atm = i; }
  });

  body.innerHTML = rows.map((r, i) =>
    `<tr class="${i === atm ? "atm" : ""}">${
      cols.map((c) => `<td>${r[c] === null ? "—" : esc(r[c])}</td>`).join("")}</tr>`).join("");
}

// --------------------------------------------------- אזהרת דוח כספי

function renderEarnings(snap, expiry) {
  if (!snap.has_earnings_before_exp || !snap.earnings_date) {
    el.earnAlert.hidden = true;
    return;
  }
  const days = snap.days_to_earnings;
  el.earnText.textContent =
    `הדוח צפוי ב-${snap.earnings_date}${days != null ? ` (בעוד ${days} ימים)` : ""}, ` +
    `כלומר לפני הפקיעה ב-${expiry}. ה-IV נוטה להתנפח לקראת הדוח ולקרוס מיד לאחריו — ` +
    `IV Crush שעלול למחוק את ערך האופציה גם כאשר כיוון המחיר צדק.`;
  el.earnAlert.hidden = false;
}

// ------------------------------------------------ היסטוריית חיפושים

const HIST_KEY = "optiradar.history";
const HIST_MAX = 5;

// כל גישה ל-localStorage עטופה: בגלישה פרטית היא זורקת חריגה
function loadHistory() {
  try {
    const raw = JSON.parse(localStorage.getItem(HIST_KEY));
    return Array.isArray(raw) ? raw.filter((s) => typeof s === "string") : [];
  } catch {
    return [];
  }
}

function renderHistory() {
  const list = loadHistory();
  if (!list.length) { el.history.hidden = true; return; }
  el.histChips.innerHTML = list
    .map((s) => `<button type="button" class="hist-chip" data-sym="${esc(s)}">${esc(s)}</button>`)
    .join("");
  el.history.hidden = false;
}

function saveHistory(symbol) {
  const list = [symbol, ...loadHistory().filter((s) => s !== symbol)].slice(0, HIST_MAX);
  try { localStorage.setItem(HIST_KEY, JSON.stringify(list)); } catch { /* אחסון חסום */ }
  renderHistory();
}

el.histChips.addEventListener("click", (ev) => {
  const chip = ev.target.closest(".hist-chip");
  if (!chip) return;
  el.symbol.value = chip.dataset.sym;
  hideSymbols();
});

// -------------------------------------------------- גרף TradingView

function renderChart(symbol) {
  el.tv.innerHTML = "";
  if (!navigator.onLine) {
    el.tv.innerHTML = `<p class="tv-fallback">הגרף דורש חיבור לרשת.</p>`;
    return;
  }

  const inner = document.createElement("div");
  inner.className = "tradingview-widget-container__widget";
  inner.style.height = "100%";
  el.tv.appendChild(inner);

  const script = document.createElement("script");
  script.type = "text/javascript";
  script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
  script.async = true;
  // הווידג'ט קורא את הגדרותיו מגוף התגית, לא מ-attribute
  script.textContent = JSON.stringify({
    autosize: true,
    symbol,
    interval: "D",
    timezone: "Asia/Jerusalem",
    theme: "dark",
    style: "1",                       // נרות יפניים
    locale: "he_IL",
    backgroundColor: "#0B0E14",
    gridColor: "rgba(42, 49, 60, 0.5)",
    withdateranges: true,
    hide_top_toolbar: false,
    hide_legend: false,
    allow_symbol_change: false,
    save_image: false,
    support_host: "https://www.tradingview.com",
  });
  script.onerror = () => {
    el.tv.innerHTML = `<p class="tv-fallback">לא ניתן לטעון את הגרף כרגע.</p>`;
  };
  el.tv.appendChild(script);
}

// ------------------------------------------------------------------ זרימה

async function loadReport(symbol, date) {
  el.aiBody.innerHTML = skeleton(5);
  try {
    const res = await fetch(`api/report?symbol=${encodeURIComponent(symbol)}&date=${date}`);
    const j = await res.json();
    if (!res.ok) {
      el.aiBody.innerHTML =
        `<p class="alert warn" style="margin:0">${esc(j.detail || "הדוח לא זמין כרגע.")}</p>`;
      return;
    }
    const tone = { "badge-up":"up", "badge-down":"down", "badge-flat":"flat" }[j.tone] || "flat";
    el.aiBody.innerHTML =
      (j.sentiment ? `<span class="badge ${tone}">סנטימנט: ${esc(j.sentiment)}</span>` : "") +
      `<div class="report">${renderMarkdown(j.report)}</div>` +
      `<p class="muted tiny" style="margin-top:.9rem">נוצר על ידי ${esc(j.model)}</p>`;
  } catch {
    el.aiBody.innerHTML = `<p class="alert warn" style="margin:0">לא ניתן להשיג את דוח האנליסט.</p>`;
  }
}

async function analyze(ev) {
  ev?.preventDefault();
  const symbol = el.symbol.value.trim().toUpperCase();
  const date = el.target.value;
  if (!symbol) return;

  el.symbol.blur();                       // סוגר את המקלדת בנייד
  el.error.hidden = true;
  el.go.disabled = true;
  el.go.textContent = "טוען…";

  // השרת בשכבה החינמית נרדם. אם התשובה מתעכבת, מסבירים במקום להשאיר מסך תקוע
  const waking = setTimeout(() => {
    showError("השרת מתעורר משינה — זה לוקח עד דקה בפעם הראשונה.", true);
  }, 4000);

  try {
    const res = await fetch(`api/analyze?symbol=${encodeURIComponent(symbol)}&date=${date}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "שגיאה בשליפת הנתונים.");

    renderHero(data.snapshot);
    renderEarnings(data.snapshot, data.expiry || data.requestedDate);
    renderLevels(data.levels);
    renderNews(data.news);
    renderChart(symbol);
    saveHistory(symbol);

    chainData = { calls:data.calls, puts:data.puts };
    el.chainMeta.textContent = data.optionsError
      ? data.optionsError
      : `פקיעה ${data.expiry} · הקרובה ביותר ל-${data.requestedDate}`;
    renderChain(document.querySelector(".seg.on").dataset.side);

    el.error.hidden = true;               // מסיר את הודעת ההתעוררות אם הופיעה
    el.results.hidden = false;
    loadReport(symbol, date);             // הדוח נטען אחרי הנתונים, לא חוסם
  } catch (err) {
    el.results.hidden = true;
    showError(err.message || "שגיאה לא צפויה.");
  } finally {
    clearTimeout(waking);
    el.go.disabled = false;
    el.go.textContent = "בצע ניתוח";
  }
}

// ------------------------------------------------------------------ אתחול

document.querySelectorAll(".seg").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".seg").forEach((b) => {
      b.classList.toggle("on", b === btn);
      b.setAttribute("aria-selected", String(b === btn));
    });
    renderChain(btn.dataset.side);
  });
});

el.form.addEventListener("submit", analyze);

// ------------------------------------------------- בוחר סימבול

const NASDAQ = [
  ["AAPL", "Apple"], ["MSFT", "Microsoft"], ["NVDA", "NVIDIA"], ["AMZN", "Amazon"],
  ["GOOGL", "Alphabet"], ["META", "Meta"], ["TSLA", "Tesla"], ["AVGO", "Broadcom"],
  ["NFLX", "Netflix"], ["AMD", "AMD"], ["COST", "Costco"], ["ADBE", "Adobe"],
  ["CSCO", "Cisco"], ["INTC", "Intel"], ["QCOM", "Qualcomm"], ["MU", "Micron"],
  ["PLTR", "Palantir"], ["QQQ", "Nasdaq 100 ETF"],
];

function renderSymbols(filter = "") {
  const f = filter.trim().toUpperCase();
  const rows = NASDAQ.filter(([sym, co]) =>
    !f || sym.includes(f) || co.toUpperCase().includes(f));

  el.symList.innerHTML = rows.length
    ? rows.map(([sym, co]) =>
        `<button type="button" class="picker-item" data-sym="${sym}">
           <span class="sym">${sym}</span><span class="co">${esc(co)}</span>
         </button>`).join("")
    : `<p class="picker-empty">אין התאמה ברשימה — אפשר להקליד כל סימבול</p>`;
}

const showSymbols = () => {
  renderSymbols(el.symbol.value);
  el.symPanel.hidden = false;
  // האיפוס חייב לבוא אחרי הסרת hidden — על אלמנט מוסתר הערך לא נתפס.
  // בלעדיו הרשימה נפתחת במקום שבו הופסקה הגלילה הקודמת.
  el.symList.scrollTop = 0;
};
const hideSymbols = () => { el.symPanel.hidden = true; };

el.symbol.addEventListener("focus", showSymbols);
el.symbol.addEventListener("input", showSymbols);

// הבחירה מוכרעת רק ב-pointerup, ורק אם האצבע כמעט לא זזה.
// preventDefault ב-pointerdown היה מבטל את מחוות הגלילה, וכל ניסיון
// לגלול נחשב לבחירה. היעד נלקח מרגע הנגיעה ולא מרגע השחרור, כי
// סגירת המקלדת מזיזה את הפריסה ועלולה להחליף את האלמנט שמתחת לאצבע.
const TAP_SLOP = 10;
let tapStart = null;

el.symList.addEventListener("pointerdown", (ev) => {
  const btn = ev.target.closest(".picker-item");
  tapStart = btn ? { btn, x: ev.clientX, y: ev.clientY } : null;
});

el.symList.addEventListener("pointercancel", () => { tapStart = null; });

el.symList.addEventListener("pointerup", (ev) => {
  const start = tapStart;
  tapStart = null;
  if (!start) return;
  if (Math.hypot(ev.clientX - start.x, ev.clientY - start.y) > TAP_SLOP) return;  // גלילה

  el.symbol.value = start.btn.dataset.sym;
  hideSymbols();
  el.symbol.blur();
});

// ------------------------------------------------- לוח שנה

const MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
                "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"];

// מקומי במכוון — toISOString היה מזיז יום אחורה באזור זמן שלפני UTC
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const midnight = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

let selected = midnight(new Date(Date.now() + 30 * 864e5));
let view = new Date(selected.getFullYear(), selected.getMonth(), 1);

function syncDate() {
  el.target.value = iso(selected);
  el.dateText.textContent =
    `${selected.getDate()} ב${MONTHS[selected.getMonth()]} ${selected.getFullYear()}`;
  const dte = Math.round((selected - midnight(new Date())) / 864e5);
  el.dateDte.textContent = `${dte} DTE`;
}

function renderCal() {
  const today = midnight(new Date());
  const y = view.getFullYear(), m = view.getMonth();
  el.calTitle.textContent = `${MONTHS[m]} ${y}`;

  const first = new Date(y, m, 1).getDay();
  const days = new Date(y, m + 1, 0).getDate();
  const cells = [];

  for (let i = 0; i < first; i++) cells.push(`<button class="cal-day blank" disabled></button>`);

  for (let d = 1; d <= days; d++) {
    const date = new Date(y, m, d);
    const cls = ["cal-day"];
    if (date.getDay() === 5) cls.push("friday");     // רוב האופציות פוקעות בשישי
    if (+date === +today) cls.push("today");
    if (+date === +selected) cls.push("sel");
    cells.push(
      `<button type="button" class="${cls.join(" ")}" data-d="${iso(date)}"${
        date < today ? " disabled" : ""}>${d}</button>`);
  }

  el.calGrid.innerHTML = cells.join("");
  el.cal.querySelector('[data-nav="-1"]').disabled =
    y === today.getFullYear() && m === today.getMonth();
}

const showCal = () => { renderCal(); el.cal.hidden = false; };
const hideCal = () => { el.cal.hidden = true; };

el.dateBtn.addEventListener("click", () => {
  hideSymbols();
  el.cal.hidden ? showCal() : hideCal();
});

el.cal.addEventListener("click", (ev) => {
  const nav = ev.target.closest(".cal-nav");
  if (nav) {
    view = new Date(view.getFullYear(), view.getMonth() + Number(nav.dataset.nav), 1);
    renderCal();
    return;
  }

  const quick = ev.target.closest("[data-days]");
  if (quick) {
    selected = midnight(new Date(Date.now() + Number(quick.dataset.days) * 864e5));
    view = new Date(selected.getFullYear(), selected.getMonth(), 1);
    syncDate();
    hideCal();
    return;
  }

  const day = ev.target.closest(".cal-day[data-d]");
  if (day && !day.disabled) {
    const [yy, mm, dd] = day.dataset.d.split("-").map(Number);
    selected = new Date(yy, mm - 1, dd);
    syncDate();
    hideCal();
  }
});

// סגירה בנגיעה מחוץ לחלוניות
document.addEventListener("pointerdown", (ev) => {
  if (!ev.target.closest("#symbol-panel, #symbol")) hideSymbols();
  if (!ev.target.closest("#cal, #date-btn")) hideCal();
});

syncDate();
renderHistory();

const netState = () => el.netdot.classList.toggle("off", !navigator.onLine);
addEventListener("online", netState);
addEventListener("offline", netState);
netState();

if ("serviceWorker" in navigator) {
  // כשגרסה חדשה של ה-worker משתלטת, הדף שרץ עדיין מחזיק את הקוד הישן
  // בזיכרון. רענון אוטומטי חוסך מהמשתמש לגלות זאת בעצמו.
  const hadController = !!navigator.serviceWorker.controller;
  let reloading = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!hadController || reloading) return;   // התקנה ראשונה — אין מה לרענן
    reloading = true;
    location.reload();
  });
  addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}

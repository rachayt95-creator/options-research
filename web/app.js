"use strict";

const $ = (id) => document.getElementById(id);
const el = { form:$("form"), symbol:$("symbol"), target:$("target"), go:$("go"),
             error:$("error"), results:$("results"), news:$("news"),
             levels:$("levels"), chain:$("chain"), chainMeta:$("chain-meta"),
             aiBody:$("ai-body"), netdot:$("netdot") };

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

  try {
    const res = await fetch(`api/analyze?symbol=${encodeURIComponent(symbol)}&date=${date}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "שגיאה בשליפת הנתונים.");

    renderHero(data.snapshot);
    renderLevels(data.levels);
    renderNews(data.news);

    chainData = { calls:data.calls, puts:data.puts };
    el.chainMeta.textContent = data.optionsError
      ? data.optionsError
      : `פקיעה ${data.expiry} · הקרובה ביותר ל-${data.requestedDate}`;
    renderChain(document.querySelector(".seg.on").dataset.side);

    el.results.hidden = false;
    loadReport(symbol, date);             // הדוח נטען אחרי הנתונים, לא חוסם
  } catch (err) {
    el.results.hidden = true;
    showError(err.message || "שגיאה לא צפויה.");
  } finally {
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

const plus30 = new Date(Date.now() + 30 * 864e5);
el.target.value = plus30.toISOString().slice(0, 10);
el.target.min = new Date().toISOString().slice(0, 10);

const netState = () => el.netdot.classList.toggle("off", !navigator.onLine);
addEventListener("online", netState);
addEventListener("offline", netState);
netState();

if ("serviceWorker" in navigator) {
  addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}

"""
מערכת מחקר אופציות — שלב 1: שליפת נתוני בסיס מ-yfinance.

הרצה:  streamlit run app.py
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
from google import genai
from google.genai import types

# ---------------------------------------------------------------- הגדרות עמוד

st.set_page_config(
    page_title="מערכת מחקר אופציות",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ------------------------------------------------------------------ PWA

APP_NAME = "מחקר אופציות"

# מוזרק אל <head> של עמוד האב. ה-iframe של components רץ עם allow-same-origin,
# ולכן window.parent.document נגיש — בלי זה המטה-תגיות היו נוחתות בתוך ה-iframe
# ולא היו משפיעות על התנהגות ה-PWA.
PWA_HEAD_SCRIPT = """
<script>
(function () {
  var doc;
  try { doc = window.parent.document; } catch (e) { doc = document; }
  if (!doc || !doc.head) { return; }

  var tags = {
    "apple-mobile-web-app-capable": "yes",
    "apple-mobile-web-app-status-bar-style": "black-translucent",
    "apple-mobile-web-app-title": "APP_NAME_PLACEHOLDER",
    "mobile-web-app-capable": "yes",
    "viewport": "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no"
  };

  Object.keys(tags).forEach(function (name) {
    var el = doc.head.querySelector('meta[name="' + name + '"]');
    if (!el) {
      el = doc.createElement("meta");
      el.setAttribute("name", name);
      doc.head.appendChild(el);
    }
    // עדכון במקום הוספה — סטרימליט כבר מגדיר viewport משלו
    el.setAttribute("content", tags[name]);
  });

  // כיווניות ברמת המסמך: תופסת גם רכיבים שנפתחים מחוץ ל-.stApp
  // (לוח השנה של בחירת התאריך, טוסטים, דיאלוגים)
  doc.documentElement.setAttribute("dir", "rtl");
  doc.documentElement.setAttribute("lang", "he");
})();
</script>
""".replace("APP_NAME_PLACEHOLDER", APP_NAME)


def inject_pwa_support() -> None:
    """מזריק את מטה-תגיות ה-PWA של Apple ואת כיווניות ה-RTL אל עמוד האב."""
    components.html(PWA_HEAD_SCRIPT, height=0)


inject_pwa_support()

# עיצוב RTL + התאמה למסכי מגע
st.markdown(
    """
    <style>
      /* ---------- בסיס RTL ומסך מגע ---------- */
      html { -webkit-text-size-adjust: 100%; }
      .stApp {
          direction: rtl;
          overscroll-behavior-y: contain;
          -webkit-tap-highlight-color: transparent;
      }
      h1, h2, h3, h4, h5, p, label, li,
      div[data-testid="stMarkdownContainer"],
      div[data-testid="stCaptionContainer"] { text-align: right; }

      div[data-testid="stAlert"] { direction: rtl; text-align: right; }

      /* מדדים: התווית בעברית מימין, המספר נשאר LTR */
      div[data-testid="stMetric"] { direction: rtl; text-align: right; }
      div[data-testid="stMetricValue"],
      div[data-testid="stMetricDelta"] { direction: ltr; }

      /* טבלאות ומספרים נשארים LTR לקריאוּת */
      div[data-testid="stDataFrame"], div[data-testid="stTable"] { direction: ltr; }

      /* ---------- גדלים נוחים למגע (מינימום 44px לפי הנחיות Apple) ---------- */
      .stButton > button {
          width: 100%; min-height: 48px; font-size: 1.05rem;
          padding: 0.6rem 1rem; border-radius: 12px;
          touch-action: manipulation;
      }
      div[data-testid="stTextInput"] input,
      div[data-testid="stDateInput"] input {
          min-height: 46px;
          font-size: 16px;   /* מתחת ל-16px iOS מזים את המסך בפוקוס על שדה */
          padding: 0.5rem 0.75rem;
      }
      div[data-baseweb="calendar"] button { min-width: 40px; min-height: 40px; }
      label { font-size: 1rem; margin-bottom: 0.3rem; }
      a, [role="tab"] { touch-action: manipulation; }

      /* טאבים: סדר RTL ושטח נגיעה מספיק */
      div[data-testid="stTabs"] [role="tablist"] { direction: rtl; }
      div[data-testid="stTabs"] [role="tab"] {
          min-height: 44px; padding: 0 1.1rem; font-size: 1rem;
      }

      /* סימבול המניה נכתב באנגלית — השדה שלו נשאר LTR */
      .st-key-symbol input {
          direction: ltr; text-align: left; letter-spacing: 0.05em;
      }

      /* רכיב הזרקת ה-PWA לא תופס מקום בעמוד */
      div[data-testid="stCustomComponentV1"] { height: 0; margin: 0; }

      /* ---------- מרווחים ---------- */
      .block-container { padding-top: 2rem; padding-bottom: 3rem; }
      @media (max-width: 640px) {
          .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
          h1 { font-size: 1.6rem; }
          div[data-testid="stMetricValue"] { font-size: 1.4rem; }
      }

      /* ---------- מצב PWA עצמאי (נוסף למסך הבית) ---------- */
      @media (display-mode: standalone) {
          .block-container {
              padding-top: calc(1.5rem + env(safe-area-inset-top, 0px));
              padding-bottom: calc(3rem + env(safe-area-inset-bottom, 0px));
          }
          header[data-testid="stHeader"], footer { display: none; }
      }

      a { word-break: break-word; }

      /* ---------- כרטיס דוח ה-AI ---------- */
      .sentiment-badge {
          display: inline-block; padding: 0.35rem 1rem; border-radius: 999px;
          font-weight: 700; font-size: 1rem; margin-bottom: 0.5rem;
      }
      .badge-up   { background: rgba(22,163,74,0.15);  color: #16a34a; border: 1px solid rgba(22,163,74,0.35); }
      .badge-down { background: rgba(220,38,38,0.15);  color: #dc2626; border: 1px solid rgba(220,38,38,0.35); }
      .badge-flat { background: rgba(100,116,139,0.15); color: #64748b; border: 1px solid rgba(100,116,139,0.35); }
      .st-key-llm_report { padding: 0.4rem 0.2rem; }
      .st-key-llm_report h2 {
          font-size: 1.15rem; margin: 1.1rem 0 0.4rem; padding-bottom: 0.3rem;
          border-bottom: 1px solid rgba(128,128,128,0.25);
      }
      .st-key-llm_report ul { padding-right: 1.2rem; padding-left: 0; }
      .st-key-llm_report li { margin-bottom: 0.45rem; line-height: 1.7; }
      .st-key-llm_report p  { line-height: 1.75; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------ שליפת נתונים

class DataFetchError(Exception):
    """שגיאה בשליפת נתונים מ-yfinance."""


def _to_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _pick_nearest_expiration(expirations: tuple[str, ...], target: dt.date) -> str:
    """בוחר את תאריך הפקיעה הקרוב ביותר לתאריך היעד שהוזן."""
    parsed = []
    for exp in expirations:
        try:
            parsed.append((dt.datetime.strptime(exp, "%Y-%m-%d").date(), exp))
        except ValueError:
            continue
    if not parsed:
        raise DataFetchError("לא נמצאו תאריכי פקיעה תקינים עבור הסימבול.")
    return min(parsed, key=lambda item: abs((item[0] - target).days))[1]


def _normalize_news(raw_news: list[dict]) -> pd.DataFrame:
    """מנרמל את מבנה החדשות של yfinance (תומך בפורמט הישן והחדש)."""
    rows = []
    for item in raw_news or []:
        content = item.get("content") if isinstance(item.get("content"), dict) else item

        title = content.get("title") or item.get("title")
        if not title:
            continue

        link = (
            item.get("link")
            or (content.get("canonicalUrl") or {}).get("url")
            or (content.get("clickThroughUrl") or {}).get("url")
            or ""
        )

        provider = content.get("provider")
        publisher = (
            provider.get("displayName") if isinstance(provider, dict) else None
        ) or item.get("publisher") or "—"

        published = content.get("pubDate") or item.get("providerPublishTime")
        if isinstance(published, (int, float)):
            published = dt.datetime.fromtimestamp(published).strftime("%Y-%m-%d %H:%M")
        elif isinstance(published, str):
            published = published.replace("T", " ").replace("Z", "")[:16]
        else:
            published = "—"

        rows.append(
            {"כותרת": title, "מקור": publisher, "פורסם": published, "קישור": link}
        )

    return pd.DataFrame(rows, columns=["כותרת", "מקור", "פורסם", "קישור"])


@st.cache_data(ttl=300, show_spinner=False)
def fetch_analysis(symbol: str, target_date: dt.date) -> dict[str, Any]:
    """
    שולף מ-yfinance עבור סימבול ותאריך יעד:
      • מחיר עדכני + רמות תמיכה/התנגדות (גבוה/נמוך 52 שבועות)
      • חדשות אחרונות (כותרות וקישורים)
      • שרשרת אופציות לתאריך הפקיעה הקרוב ביותר לתאריך היעד
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise DataFetchError("יש להזין סימבול מניה.")

    ticker = yf.Ticker(symbol)

    # --- היסטוריית שנה: בסיס למחיר ולרמות התמיכה/התנגדות
    history = ticker.history(period="1y", auto_adjust=False)
    if history.empty:
        raise DataFetchError(f"לא נמצאו נתוני מסחר עבור הסימבול '{symbol}'.")

    try:
        info = ticker.info or {}
    except Exception:
        info = {}

    last_close = _to_float(history["Close"].iloc[-1])
    price = _to_float(getattr(ticker.fast_info, "last_price", None)) or last_close

    prev_close = _to_float(history["Close"].iloc[-2]) if len(history) > 1 else None
    change_pct = (
        ((price - prev_close) / prev_close * 100)
        if price is not None and prev_close
        else None
    )

    high_52w = _to_float(info.get("fiftyTwoWeekHigh")) or _to_float(history["High"].max())
    low_52w = _to_float(info.get("fiftyTwoWeekLow")) or _to_float(history["Low"].min())

    # תמיכה/התנגדות קצרות טווח: גבוה/נמוך של 3 החודשים האחרונים
    recent = history.tail(63)
    resistance_3m = _to_float(recent["High"].max())
    support_3m = _to_float(recent["Low"].min())

    snapshot = {
        "symbol": symbol,
        "name": info.get("shortName") or info.get("longName") or symbol,
        "currency": info.get("currency", "USD"),
        "price": price,
        "change_pct": change_pct,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "resistance_3m": resistance_3m,
        "support_3m": support_3m,
        "last_update": history.index[-1].strftime("%Y-%m-%d"),
    }

    levels = pd.DataFrame(
        [
            {"רמה": "התנגדות — שיא 52 שבועות", "מחיר": high_52w},
            {"רמה": "התנגדות — שיא 3 חודשים", "מחיר": resistance_3m},
            {"רמה": "מחיר נוכחי", "מחיר": price},
            {"רמה": "תמיכה — שפל 3 חודשים", "מחיר": support_3m},
            {"רמה": "תמיכה — שפל 52 שבועות", "מחיר": low_52w},
        ]
    )
    levels["מרחק מהמחיר %"] = levels["מחיר"].apply(
        lambda x: round((x - price) / price * 100, 2)
        if price and x is not None
        else None
    )
    levels["מחיר"] = levels["מחיר"].apply(lambda x: round(x, 2) if x else None)

    # --- חדשות
    try:
        news = _normalize_news(ticker.news)
    except Exception:
        news = pd.DataFrame(columns=["כותרת", "מקור", "פורסם", "קישור"])

    # --- שרשרת אופציות
    options_error = None
    selected_expiry = None
    calls = puts = pd.DataFrame()
    try:
        expirations = ticker.options
        if not expirations:
            options_error = "לא נמצאו אופציות סחירות עבור סימבול זה."
        else:
            selected_expiry = _pick_nearest_expiration(tuple(expirations), target_date)
            chain = ticker.option_chain(selected_expiry)
            calls = _clean_chain(chain.calls)
            puts = _clean_chain(chain.puts)
    except DataFetchError as exc:
        options_error = str(exc)
    except Exception as exc:
        options_error = f"שגיאה בשליפת שרשרת האופציות: {exc}"

    return {
        "snapshot": snapshot,
        "levels": levels,
        "news": news,
        "expiry": selected_expiry,
        "calls": calls,
        "puts": puts,
        "options_error": options_error,
    }


def _clean_chain(df: pd.DataFrame) -> pd.DataFrame:
    """משאיר את העמודות המשמעותיות בשרשרת האופציות ומתרגם כותרות."""
    columns = {
        "strike": "סטרייק",
        "lastPrice": "מחיר אחרון",
        "bid": "ביקוש",
        "ask": "היצע",
        "volume": "מחזור",
        "openInterest": "ריבית פתוחה",
        "impliedVolatility": "IV",
    }
    existing = [c for c in columns if c in df.columns]
    out = df[existing].copy().rename(columns=columns)
    if "IV" in out.columns:
        out["IV"] = (out["IV"] * 100).round(1)
    for col in ("מחזור", "ריבית פתוחה"):
        if col in out.columns:
            out[col] = out[col].fillna(0).astype(int)
    return out.round(2).reset_index(drop=True)


# ------------------------------------------------------------ ניתוח Gemini

GEMINI_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """אתה אנליסט מחקר מוביל (Lead Research Analyst) המתמחה בשוק האופציות האמריקאי, \
וכותב עבור סוחרי אופציות מקצועיים.

הקלט שתקבל: חדשות אחרונות על המניה, מחיר המניה ורמות טכניות, ותאריך הפקיעה המבוקש.

כללי כתיבה מחייבים:
1. כתוב בעברית בלבד, בשפה מקצועית ורהוטה ברמת שפת אם. אל תשתמש באנגלית מלבד המונחים המקצועיים שלהלן.
2. חוק מונחים — אסור לתרגם מונחי מסחר לעברית. השאר אותם באנגלית בתוך המשפט העברי:
   Call, Put, Strike, IV, Theta, Bullish, Bearish, DTE, Credit Spread, Debit Spread.
   דוגמה לניסוח נכון: "רמת ה-IV הגבוהה מעדיפה Credit Spread מבוסס Put מתחת לתמיכה".
3. אל תמציא נתונים. אם נתון חסר או לא סופק לך — ציין זאת במפורש במקום לנחש.
4. זהו מחקר בלבד ולא ייעוץ השקעות. אל תיתן הוראת קנייה או מכירה מחייבת.

מבנה הדוח — השתמש בכותרות Markdown בדיוק בסדר ובניסוח הבא:

## סנטימנט
שורה אחת בלבד: בחר אחת מהאפשרויות — עלייה / ירידה / דשדוש / עלייה ודשדוש / ירידה ודשדוש — \
ולאחריה מקף ומשפט הנמקה קצר.

## נקודות מפתח
3-4 נקודות (bullets). כל נקודה מנתחת גורם מהותי אחד — חדשה, אירוע צפוי או מבנה טכני — \
ואת השפעתו הצפויה בטווח הזמן שעד תאריך הפקיעה.

## הערכת כיוון
טווח המחירים הצפוי עד הפקיעה במספרים קונקרטיים, ורמות התמיכה וההתנגדות המרכזיות למעקב.

## דגשים לסוחר האופציות
טיפים מעשיים: התייחס לרמת ה-IV הנוכחית, לסיכון IV Crush אם צפוי דוח כספי או אירוע מהותי לפני הפקיעה, \
להשפעת Theta לפי מספר ה-DTE שנותרו, ולסוג המבנה המתאים לתרחיש."""


class LLMError(Exception):
    """שגיאה בתקשורת מול Gemini."""


def get_api_key() -> str | None:
    """מפתח Gemini — קודם מ-st.secrets, ואם אין אז ממשתנה סביבה."""
    try:
        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            return str(key).strip()
    except Exception:
        pass  # אין קובץ secrets.toml — ממשיכים למשתנה הסביבה
    return (os.environ.get("GEMINI_API_KEY") or "").strip() or None


def _chain_stats(data: dict[str, Any]) -> str:
    """מסכם את שרשרת האופציות: IV קרוב לכסף, ריבית פתוחה ויחס Put/Call."""
    calls, puts = data.get("calls"), data.get("puts")
    price = data["snapshot"]["price"]
    if calls is None or puts is None or calls.empty or puts.empty or not price:
        return "שרשרת אופציות: לא זמינה."

    lines = []
    for label, df in (("Call", calls), ("Put", puts)):
        atm = df.iloc[(df["סטרייק"] - price).abs().argsort().iloc[0]]
        lines.append(
            f"- {label} ATM (Strike {atm['סטרייק']:.1f}): IV {atm.get('IV', float('nan')):.1f}%, "
            f"מחיר אחרון {atm.get('מחיר אחרון', float('nan')):.2f}, "
            f"ריבית פתוחה {int(atm.get('ריבית פתוחה', 0))}"
        )

    call_oi, put_oi = int(calls["ריבית פתוחה"].sum()), int(puts["ריבית פתוחה"].sum())
    ratio = f"{put_oi / call_oi:.2f}" if call_oi else "—"
    lines.append(f"- ריבית פתוחה כוללת: Call {call_oi:,} מול Put {put_oi:,} (יחס Put/Call: {ratio})")
    return "שרשרת אופציות:\n" + "\n".join(lines)


def build_llm_context(data: dict[str, Any], target_date: dt.date) -> str:
    """בונה את הודעת המשתמש ל-Gemini מתוך הנתונים שנשאבו מ-yfinance."""
    snap = data["snapshot"]
    expiry = data.get("expiry")
    dte = (dt.datetime.strptime(expiry, "%Y-%m-%d").date() - dt.date.today()).days if expiry else None

    parts = [
        f"מניה: {snap['name']} ({snap['symbol']}), מטבע {snap['currency']}.",
        f"מחיר נוכחי: {snap['price']:.2f} (נכון ל-{snap['last_update']}).",
    ]
    if snap.get("change_pct") is not None:
        parts.append(f"שינוי יומי אחרון: {snap['change_pct']:.2f}%.")

    parts.append(
        "רמות טכניות:\n"
        f"- שיא 52 שבועות: {snap['high_52w']:.2f}\n"
        f"- שפל 52 שבועות: {snap['low_52w']:.2f}\n"
        f"- התנגדות 3 חודשים: {snap['resistance_3m']:.2f}\n"
        f"- תמיכה 3 חודשים: {snap['support_3m']:.2f}"
    )

    parts.append(
        f"תאריך יעד שביקש הסוחר: {target_date:%Y-%m-%d}. "
        + (
            f"תאריך הפקיעה הסחיר הקרוב ביותר: {expiry}, כלומר {dte} DTE."
            if expiry
            else "לא נמצא תאריך פקיעה סחיר."
        )
    )
    parts.append(_chain_stats(data))

    news = data.get("news")
    if news is not None and not news.empty:
        headlines = "\n".join(
            f"- [{row['פורסם']}] {row['כותרת']} ({row['מקור']})"
            for _, row in news.head(10).iterrows()
        )
        parts.append(f"חדשות אחרונות:\n{headlines}")
    else:
        parts.append("חדשות אחרונות: לא נמצאו.")

    parts.append("כתוב את דוח המחקר לפי המבנה והכללים שהוגדרו לך.")
    return "\n\n".join(parts)


@st.cache_data(ttl=1800, show_spinner=False)
def _generate_report(prompt: str, api_key: str) -> str:
    """קריאה בפועל ל-Gemini. ממוטמנת כדי לא לבזבז קריאות על אותו קלט."""
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.4,
            max_output_tokens=2048,
        ),
    )
    text = (response.text or "").strip()
    if not text:
        raise LLMError("Gemini החזיר תשובה ריקה. נסה שוב בעוד רגע.")
    return text


def analyze_with_llm(data: dict[str, Any], target_date: dt.date) -> str:
    """
    מקבל את הנתונים שנשאבו מ-yfinance ומחזיר דוח מחקר בעברית מ-Gemini.
    זורק LLMError אם אין מפתח או אם הקריאה נכשלה.
    """
    api_key = get_api_key()
    if not api_key:
        raise LLMError(
            "לא נמצא מפתח GEMINI_API_KEY. הגדר אותו ב-.streamlit/secrets.toml "
            "או כמשתנה סביבה."
        )
    try:
        return _generate_report(build_llm_context(data, target_date), api_key)
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError(f"הקריאה ל-Gemini נכשלה: {exc}") from exc


def _sentiment_badge(report: str) -> tuple[str, str] | None:
    """מחלץ את שורת הסנטימנט מהדוח ומחזיר (טקסט, מחלקת CSS) לתצוגת תגית."""
    after = report.split("## סנטימנט", 1)
    if len(after) < 2:
        return None
    line = next((ln.strip() for ln in after[1].splitlines() if ln.strip()), "")
    if not line:
        return None

    head = line.split("—")[0].split("-")[0].strip(" *#:")
    for label, css in (
        ("עלייה ודשדוש", "badge-flat"),
        ("ירידה ודשדוש", "badge-flat"),
        ("דשדוש", "badge-flat"),
        ("עלייה", "badge-up"),
        ("ירידה", "badge-down"),
    ):
        if label in head:
            return head or label, css
    return head, "badge-flat"


# ------------------------------------------------------------------- ממשק

st.title("📈 מערכת מחקר אופציות")
st.caption("שלב 1 — שליפת נתוני בסיס, חדשות ושרשרת אופציות")

symbol_input = st.text_input(
    "סימבול מניה",
    value="AAPL",
    key="symbol",
    placeholder="לדוגמה: AAPL, TSLA, NVDA",
    help="סימבול המניה בבורסה האמריקאית",
).strip().upper()

target_date = st.date_input(
    "תאריך יעד / פקיעה",
    key="target",
    value=dt.date.today() + dt.timedelta(days=30),
    min_value=dt.date.today(),
    help="המערכת תבחר את תאריך הפקיעה הסחיר הקרוב ביותר לתאריך זה",
)

analyze = st.button("בצע ניתוח ראשוני", type="primary")

if analyze:
    if not symbol_input:
        st.warning("יש להזין סימבול מניה.")
        st.stop()

    with st.spinner(f"שולף נתונים עבור {symbol_input}..."):
        try:
            fetched = fetch_analysis(symbol_input, target_date)
        except DataFetchError as exc:
            st.session_state.pop("analysis", None)
            st.error(str(exc))
            st.stop()
        except Exception as exc:
            st.session_state.pop("analysis", None)
            st.error(f"שגיאה בשליפת הנתונים: {exc}")
            st.stop()

    st.session_state["analysis"] = {"data": fetched, "target_date": target_date}

state = st.session_state.get("analysis")

if not state:
    st.info("הזן סימבול ותאריך יעד, ולחץ על **בצע ניתוח ראשוני**.")
    st.stop()

data = state["data"]
requested_date = state["target_date"]
snap = data["snapshot"]

# --- כרטיס מחיר
st.subheader(f"{snap['name']} ({snap['symbol']})")
col1, col2, col3 = st.columns(3)
col1.metric(
    "מחיר נוכחי",
    f"{snap['price']:.2f}" if snap["price"] else "—",
    f"{snap['change_pct']:.2f}%" if snap["change_pct"] is not None else None,
)
col2.metric("שיא 52 שבועות", f"{snap['high_52w']:.2f}" if snap["high_52w"] else "—")
col3.metric("שפל 52 שבועות", f"{snap['low_52w']:.2f}" if snap["low_52w"] else "—")
st.caption(f"מטבע: {snap['currency']} · עדכון אחרון: {snap['last_update']}")

# --- רמות תמיכה והתנגדות
st.markdown("### רמות תמיכה והתנגדות")
st.dataframe(data["levels"], use_container_width=True, hide_index=True)

# --- חדשות
st.markdown("### חדשות אחרונות")
news_df = data["news"]
if news_df.empty:
    st.info("לא נמצאו חדשות עדכניות עבור סימבול זה.")
else:
    st.dataframe(
        news_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "כותרת": st.column_config.TextColumn(width="large"),
            "קישור": st.column_config.LinkColumn("קישור", display_text="פתח ↗"),
        },
    )

# --- שרשרת אופציות
st.markdown("### שרשרת אופציות")
if data["options_error"]:
    st.warning(data["options_error"])
else:
    st.caption(
        f"תאריך פקיעה נבחר: **{data['expiry']}** "
        f"(הקרוב ביותר לתאריך היעד {requested_date:%Y-%m-%d})"
    )
    calls_tab, puts_tab = st.tabs(["CALL", "PUT"])
    with calls_tab:
        st.dataframe(data["calls"], use_container_width=True, hide_index=True)
    with puts_tab:
        st.dataframe(data["puts"], use_container_width=True, hide_index=True)

# --- דוח אנליסט AI
st.markdown("### 🤖 דוח אנליסט AI")

if not get_api_key():
    st.warning(
        "כדי להפיק את דוח האנליסט יש להגדיר מפתח **GEMINI_API_KEY** — "
        "בקובץ `.streamlit/secrets.toml` או כמשתנה סביבה. "
        "מפתח חינמי זמין ב-Google AI Studio."
    )
else:
    with st.spinner("Gemini מנתח את הנתונים..."):
        try:
            report = analyze_with_llm(data, requested_date)
        except LLMError as exc:
            report = None
            st.error(str(exc))

    if report:
        with st.container(border=True, key="llm_report"):
            badge = _sentiment_badge(report)
            if badge:
                label, css = badge
                st.markdown(
                    f'<span class="sentiment-badge {css}">סנטימנט: {label}</span>',
                    unsafe_allow_html=True,
                )
            st.markdown(report)
            st.caption(
                f"נוצר על ידי {GEMINI_MODEL} · מחקר בלבד, אינו מהווה ייעוץ השקעות."
            )

st.success("הניתוח הראשוני הושלם.")

"""
מערכת מחקר אופציות — שלב 1: שליפת נתוני בסיס מ-yfinance.

הרצה:  streamlit run app.py
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

import research

# הלוגיקה חיה ב-research.py ומשותפת עם ה-API. כאן רק שכבת התצוגה.
DataFetchError = research.DataFetchError
LLMError = research.LLMError
GEMINI_MODEL = research.GEMINI_MODEL
_sentiment_badge = research._sentiment_badge

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


# ------------------------------------------------ עטיפות מטמון של Streamlit

@st.cache_data(ttl=300, show_spinner=False)
def fetch_analysis(symbol: str, target_date: dt.date) -> dict[str, Any]:
    return research.fetch_analysis(symbol, target_date)


def get_api_key() -> str | None:
    """מעדיף את st.secrets, ומזין אותו לסביבה כדי ש-research יראה את אותו מפתח."""
    try:
        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            os.environ["GEMINI_API_KEY"] = str(key).strip()
    except Exception:
        pass  # אין קובץ secrets.toml — ממשיכים למשתנה הסביבה
    return research.get_api_key()


@st.cache_data(ttl=1800, show_spinner=False)
def _cached_report(symbol: str, target_date: dt.date, _data: dict[str, Any]) -> str:
    # הקידומת _ ב-_data מונעת מ-Streamlit לנסות לגבב DataFrames
    return research.analyze_with_llm(_data, target_date)


def analyze_with_llm(data: dict[str, Any], target_date: dt.date) -> str:
    get_api_key()
    return _cached_report(data["snapshot"]["symbol"], target_date, data)


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

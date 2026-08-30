"""
לוגיקת המחקר — שכבה טהורה, ללא תלות בממשק.

נצרכת גם על ידי app.py (Streamlit) וגם על ידי api/main.py (FastAPI),
כדי שלא יתקיימו שני עותקים של אותה לוגיקה.
"""

from __future__ import annotations

import datetime as dt
import math
import os
from typing import Any

import pandas as pd
import yfinance as yf
from google import genai
from google.genai import types


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

GEMINI_MODEL = "gemini-3.6-flash"

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


def _load_dotenv(path: str = ".env") -> None:
    """
    טוען .env אם קיים, בלי תלות חיצונית. משתני סביבה אמיתיים גוברים,
    כדי שהגדרות הפריסה (Render) תמיד ינצחו קובץ מקומי.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass  # אין קובץ .env — זה המצב הרגיל בפריסה


_load_dotenv()


def get_api_key() -> str | None:
    """מפתח Gemini ממשתנה הסביבה. שכבת הסודות של Streamlit נוספת מעל, ב-app.py."""
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


def _generate_report(prompt: str, api_key: str) -> str:
    """קריאה בפועל ל-Gemini. ממוטמנת כדי לא לבזבז קריאות על אותו קלט."""
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.4,
            # מודל חשיבה: ה-thinking נגרע מתקציב הפלט. עם תקציב צר מדי
            # הדוח נחתך באמצע משפט, ולכן חלון רחב וגג מפורש לחשיבה.
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=2048),
        ),
    )

    text = (response.text or "").strip()
    if not text:
        raise LLMError("Gemini החזיר תשובה ריקה. נסה שוב בעוד רגע.")

    # דוח קטוע גרוע מדוח חסר — עדיף להיכשל בקול
    candidates = response.candidates or []
    if candidates and str(getattr(candidates[0], "finish_reason", "")).endswith("MAX_TOKENS"):
        raise LLMError("הדוח נקטע באמצע. נסה שוב, או הקטן את היקף הנתונים.")

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


# ------------------------------------------------------------ סריאליזציה

def _clean_value(value: Any) -> Any:
    """NaN/NaT אינם חוקיים ב-JSON — מומרים ל-None."""
    if value is None:
        return None
    if hasattr(value, "item"):          # טיפוסי numpy
        try:
            value = value.item()
        except (ValueError, AttributeError):
            return str(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    return [
        {str(k): _clean_value(v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def to_payload(data: dict[str, Any]) -> dict[str, Any]:
    """ממיר את תוצאת fetch_analysis למבנה JSON-safe עבור ה-API."""
    return {
        "snapshot": {k: _clean_value(v) for k, v in data["snapshot"].items()},
        "levels": _records(data.get("levels")),
        "news": _records(data.get("news")),
        "expiry": data.get("expiry"),
        "calls": _records(data.get("calls")),
        "puts": _records(data.get("puts")),
        "optionsError": data.get("options_error"),
    }

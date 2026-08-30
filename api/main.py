"""
שכבת ה-API. עוטפת את research.py ומגישה את הפרונט הסטטי מתוך web/.

הרצה:  uvicorn api.main:app --reload
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any, Dict, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import research

app = FastAPI(title="OptiRadar", docs_url="/api/docs")

WEB_DIR = "web"
DATA_TTL = 300      # 5 דקות — נתוני מסחר
REPORT_TTL = 1800   # 30 דקות — דוח Gemini, כדי לחסוך במכסה החינמית

_cache: Dict[Tuple[str, ...], Tuple[float, Any]] = {}


def _cached(key: Tuple[str, ...], ttl: int, producer):
    """מטמון TTL פשוט בזיכרון — מחליף את st.cache_data שאיננו כאן."""
    hit = _cache.get(key)
    now = time.time()
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = producer()
    _cache[key] = (now, value)
    return value


def _parse_date(value: Optional[str]) -> dt.date:
    if not value:
        return dt.date.today() + dt.timedelta(days=30)
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "תאריך לא תקין. הפורמט הנדרש הוא YYYY-MM-DD.")


def _load(symbol: str, target: dt.date) -> dict:
    symbol = (symbol or "").strip().upper()
    if not symbol or len(symbol) > 12:
        raise HTTPException(400, "סימבול לא תקין.")
    try:
        return _cached(
            ("data", symbol, target.isoformat()),
            DATA_TTL,
            lambda: research.fetch_analysis(symbol, target),
        )
    except research.DataFetchError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(502, f"שגיאה בשליפת הנתונים: {exc}")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "hasGeminiKey": bool(research.get_api_key())}


@app.get("/api/analyze")
def analyze(
    symbol: str = Query(..., description="סימבול מניה, למשל AAPL"),
    date: Optional[str] = Query(None, description="תאריך יעד YYYY-MM-DD"),
) -> JSONResponse:
    """נתוני המסחר, הרמות, החדשות ושרשרת האופציות."""
    target = _parse_date(date)
    payload = research.to_payload(_load(symbol, target))
    payload["requestedDate"] = target.isoformat()
    return JSONResponse(payload)


@app.get("/api/report")
def report(
    symbol: str = Query(...),
    date: Optional[str] = Query(None),
) -> JSONResponse:
    """דוח האנליסט מ-Gemini. נפרד מ-/api/analyze כדי שהנתונים יוצגו מיד."""
    target = _parse_date(date)
    data = _load(symbol, target)

    def produce() -> dict:
        text = research.analyze_with_llm(data, target)
        badge = research._sentiment_badge(text)
        return {
            "report": text,
            "sentiment": badge[0] if badge else None,
            "tone": badge[1] if badge else None,
            "model": research.GEMINI_MODEL,
        }

    try:
        return JSONResponse(
            _cached(("report", symbol.strip().upper(), target.isoformat()), REPORT_TTL, produce)
        )
    except research.LLMError as exc:
        raise HTTPException(503, str(exc))


# הפרונט מוגש אחרון, כדי שלא יבלע את נתיבי ה-API
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

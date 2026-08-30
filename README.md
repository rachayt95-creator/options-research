# 📡 OptiRadar

ניתוח מניות ואופציות בעברית: נתוני מסחר, רמות תמיכה/התנגדות, חדשות ושרשרת
אופציות מ-yfinance, ודוח אנליסט שנכתב על ידי Google Gemini.

לפרויקט **שני ממשקים מעל אותה לוגיקה**:

| | קובץ | מתי להשתמש |
|---|---|---|
| 🚀 **אפליקציה** | `api/` + `web/` | חוויית PWA מלאה, נייד. ההמלצה. |
| 🧪 **Streamlit** | `app.py` | פרוטוטייפ מהיר, בדיקות נתונים |

```
research.py          כל הלוגיקה — yfinance + Gemini. ללא תלות בממשק.
api/main.py          FastAPI: JSON + הגשת הפרונט
web/                 PWA: HTML/CSS/JS, service worker, manifest, אייקונים
app.py               גרסת Streamlit (עוטפת את research.py)
```

`research.py` הוא מקור אמת אחד — שני הממשקים קוראים לו, ואין שני עותקים של
הלוגיקה שיכולים להיפרד זה מזה.

## הרצה

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# מפתח חינמי: https://aistudio.google.com/apikey
echo 'GEMINI_API_KEY="AIza-המפתח-שלך"' > .env

.venv/bin/uvicorn api.main:app --reload --port 8000
```

פתח http://localhost:8000 — זו האפליקציה.

`.env` מוחרג ב-`.gitignore`. משתנה סביבה אמיתי גובר עליו, כך שבפריסה
מספיק להגדיר `GEMINI_API_KEY` בהגדרות השירות.
לגרסת Streamlit: `.venv/bin/streamlit run app.py`.

### התקנה כאפליקציה באייפון

פתח את הכתובת ב-Safari ➜ שתף ➜ **הוסף למסך הבית**. היא תיפתח במסך מלא, בלי
שורת כתובת, עם אייקון משלה ועם מעטפת שנשמרת במטמון כך שהפתיחה מיידית.
לשם כך נדרש **HTTPS** — כלומר לאחר פריסה, לא מ-localhost.

## API

| נתיב | תיאור |
|---|---|
| `GET /api/analyze?symbol=AAPL&date=2026-09-29` | מחיר, רמות, חדשות ושרשרת אופציות |
| `GET /api/report?symbol=AAPL&date=2026-09-29` | דוח האנליסט מ-Gemini |
| `GET /api/health` | בדיקת חיים + האם מוגדר מפתח |
| `GET /api/docs` | תיעוד אינטראקטיבי |

הנתונים נשמרים במטמון ל-5 דקות והדוח ל-30 דקות, כדי לחסוך במכסת ה-API החינמית.

## העלאה ל-GitHub

צור מאגר **ריק** ב-https://github.com/new (בלי README ובלי .gitignore), ואז:

```bash
git remote add origin https://github.com/<שם-משתמש>/<מאגר>.git
git push -u origin main
```

`.gitignore` מחריג את `.venv/` ואת `.streamlit/secrets.toml`. ודא לפני דחיפה:

```bash
git status --porcelain | grep secrets.toml    # לא אמור להחזיר כלום
```

## פריסה

### את האפליקציה — Render (שכבה חינמית)

1. https://render.com ➜ התחבר עם GitHub ➜ **New ➜ Web Service**.
2. בחר את המאגר.
3. הגדרות:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
4. **Environment ➜ Add Environment Variable**: `GEMINI_API_KEY` = המפתח שלך.
5. **Create Web Service**. בסיום תקבל כתובת `https://<שם>.onrender.com` עם
   HTTPS — ומשם אפשר להתקין למסך הבית.

> בשכבה החינמית השירות נרדם אחרי 15 דקות חוסר פעילות, והבקשה הראשונה
> לאחר מכן אורכת כדקה.

### את גרסת Streamlit — Streamlit Community Cloud

https://share.streamlit.io ➜ **Create app** ➜ בחר את המאגר, ענף `main`,
**Main file path** = `app.py`, וב-**Advanced settings ➜ Secrets** הדבק:

```toml
GEMINI_API_KEY = "AIza-המפתח-שלך"
```

## מגבלות ידועות

- Yahoo Finance מגביל בקשות מכתובות IP של ספקי ענן. ייתכנו כשלי שליפה
  בפריסה שעובדים מצוין מקומית.
- Yahoo אינו שולח הידרי CORS, ולכן חובה שרת באמצע — אי אפשר לבנות את זה
  כאתר סטטי בלבד.

> מחקר בלבד. אינו מהווה ייעוץ השקעות.

# 📈 מערכת מחקר אופציות

אפליקציית Streamlit בעברית לניתוח מניות ואופציות: שולפת נתוני מסחר, רמות
תמיכה/התנגדות, חדשות ושרשרת אופציות מ-yfinance, ומפיקה דוח אנליסט בעברית
באמצעות Google Gemini. הממשק מותאם לנייד ולהתקנה כ-PWA במכשירי iOS.

## מבנה הפרויקט

```
app.py                            כל הלוגיקה והממשק
requirements.txt                  תלויות
.streamlit/config.toml            ערכת נושא כהה
.streamlit/secrets.toml.template  תבנית למפתח ה-API
.streamlit/secrets.toml           המפתח האמיתי — לא עולה ל-git
```

## הרצה מקומית

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .streamlit/secrets.toml.template .streamlit/secrets.toml
# ערוך את הקובץ והכנס מפתח מ-https://aistudio.google.com/apikey

.venv/bin/streamlit run app.py
```

לחלופין, במקום קובץ הסודות: `export GEMINI_API_KEY="..."`.

---

## שלב 1 — העלאה ל-GitHub

צור מאגר **ריק** בכתובת https://github.com/new (בלי README ובלי .gitignore —
הם כבר קיימים כאן), ואז מתוך תיקיית הפרויקט:

```bash
git init
git add .
git commit -m "מערכת מחקר אופציות"
git branch -M main
git remote add origin https://github.com/<שם-המשתמש>/<שם-המאגר>.git
git push -u origin main
```

לפני ה-push, ודא שהמפתח לא נכלל:

```bash
git status --porcelain | grep secrets.toml   # לא אמור להחזיר כלום
```

הקובץ `.gitignore` כבר מחריג את `.venv/`, את `__pycache__/` ואת
`.streamlit/secrets.toml`. **התבנית** (`secrets.toml.template`) כן נכנסת
למאגר — היא לא מכילה מפתח.

המאגר יכול להיות ציבורי או פרטי; ב-Streamlit Cloud החינמי שניהם נתמכים.

## שלב 2 — פריסה ל-Streamlit Community Cloud

1. היכנס ל-https://share.streamlit.io והתחבר עם חשבון ה-GitHub שלך.
2. בפעם הראשונה אשר ל-Streamlit גישה למאגרים (`Authorize`). למאגר פרטי יש
   לאשר גם את הרשאת ה-private repositories.
3. לחץ **Create app** ובחר **Deploy a public app from GitHub**.
4. מלא את הפרטים:
   - **Repository**: `<שם-המשתמש>/<שם-המאגר>`
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL**: הכתובת שתקבל, בפורמט `<שם>.streamlit.app`
5. פתח **Advanced settings ➜ Secrets** והדבק שורה אחת:

   ```toml
   GEMINI_API_KEY = "AIza-המפתח-שלך"
   ```

   הסודות נשמרים אצל Streamlit ואינם עוברים דרך המאגר. `st.secrets` באפליקציה
   יקרא אותם בדיוק כמו מקובץ מקומי.
6. ב-**Advanced settings** בחר גם **Python 3.11** ומעלה.
7. לחץ **Deploy**. הבנייה נמשכת 2-4 דקות; בסיום האפליקציה זמינה בכתובת
   `https://<שם>.streamlit.app`.

### עדכון האפליקציה

כל `git push` ל-`main` מפעיל פריסה מחדש אוטומטית. לשינוי מפתח ה-API אין צורך
ב-push — רק **App settings ➜ Secrets ➜ Save**, והאפליקציה תופעל מחדש.

### תקלות נפוצות

| תופעה | סיבה וטיפול |
|---|---|
| האזהרה "לא נמצא מפתח GEMINI_API_KEY" | הסוד לא הוגדר, או שהודבק בלי מירכאות. בדוק ב-App settings ➜ Secrets. |
| "לא נמצאו נתוני מסחר עבור הסימבול" | Yahoo Finance מגביל לעיתים בקשות מכתובות IP של שרתי ענן. נסה שוב מאוחר יותר. |
| האפליקציה נרדמת | אפליקציות חינמיות נכנסות לשינה אחרי חוסר פעילות; הכניסה הראשונה מעירה אותן תוך כדקה. |

> מחקר בלבד. אינו מהווה ייעוץ השקעות.

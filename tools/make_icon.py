"""
מחולל אייקון OptiRadar — מכ"ם עם אלומת סריקה ומטרות.

הרצה מתיקיית השורש:  .venv/bin/python tools/make_icon.py
numpy לרנדור עם supersampling, וה-PNG נכתב ידנית ללא תלות נוספת.
"""
import numpy as np, zlib, struct
BG    = np.array([0x0B, 0x0E, 0x14]) / 255
DISC  = np.array([0x10, 0x1B, 0x24]) / 255
RING  = np.array([0x3C, 0x51, 0x60]) / 255
AMBER = np.array([0xF0, 0xB4, 0x29]) / 255
GREEN = np.array([0x3F, 0xD3, 0x7B]) / 255

SS = 4                      # supersampling — בלי זה העיגולים משוננים
R_OUT = 0.385               # בתוך אזור הבטיחות של maskable (רדיוס 0.4)
LEAD  = np.deg2rad(-38)     # קצה מוביל של הסריקה
SPAN  = np.deg2rad(85)


def over(dst, color, alpha):
    """אלפא-קומפוזיטינג: alpha הוא מערך (h,w), color הוא RGB."""
    a = alpha[..., None]
    return dst * (1 - a) + color * a


def band(value, target, width, soft):
    """טבעת רכה סביב target — משמש לקווים מוחלקים."""
    d = np.abs(value - target)
    return np.clip(1 - (d - width) / soft, 0, 1)


def render(n):
    m = n * SS
    ax = (np.arange(m) + 0.5) / m
    x, y = np.meshgrid(ax, ax)
    dx, dy = x - 0.5, y - 0.5
    r = np.hypot(dx, dy)
    th = np.arctan2(dy, dx)

    px = 1.0 / m                                  # רוחב פיקסל, ליחידת החלקה
    img = np.broadcast_to(BG, (m, m, 3)).copy()

    # דיסקת המכ"ם, עם התכהות קלה כלפי השוליים
    disc = np.clip((R_OUT - r) / px, 0, 1)
    shade = DISC * (1 - 0.35 * np.clip(r / R_OUT, 0, 1))[..., None]
    img = img * (1 - disc[..., None]) + shade * disc[..., None]

    # צלב כוונת
    cross = np.maximum(
        band(np.abs(dy), 0, 0.0018, 0.0022) * (r < R_OUT * 0.96),
        band(np.abs(dx), 0, 0.0018, 0.0022) * (r < R_OUT * 0.96),
    )
    img = over(img, RING, cross * 0.62)

    # טבעות פנימיות
    for rad in (0.13, 0.26):
        img = over(img, RING, band(r, rad, 0.0019, 0.0026) * 0.95)

    # אלומת הסריקה — דוהה אחורה מהקצה המוביל
    delta = (LEAD - th) % (2 * np.pi)
    inside = (delta < SPAN) & (r < R_OUT)
    fade = np.where(inside, np.clip(1 - delta / SPAN, 0, 1) ** 1.35, 0)
    img = over(img, AMBER, fade * 0.66)

    # הקו המוביל עצמו, בהיר
    img = over(img, AMBER, band(delta, 0, 0.004, 0.006) * (r < R_OUT) * 0.95)

    # מטרה שזוהתה: הילה ירוקה ונקודה
    bx, by = 0.5 + 0.205 * np.cos(LEAD + 0.30), 0.5 + 0.205 * np.sin(LEAD + 0.30)
    bd = np.hypot(x - bx, y - by)
    img = over(img, GREEN, np.clip(1 - bd / 0.088, 0, 1) ** 2.4 * 0.62)   # הילה
    img = over(img, GREEN, np.clip((0.035 - bd) / px, 0, 1))              # נקודה

    # מטרה שנייה, עמומה
    sx, sy = 0.5 + 0.30 * np.cos(np.deg2rad(150)), 0.5 + 0.30 * np.sin(np.deg2rad(150))
    sd = np.hypot(x - sx, y - sy)
    img = over(img, GREEN, np.clip((0.020 - sd) / px, 0, 1) * 0.45)

    # טבעת חיצונית
    img = over(img, AMBER, band(r, R_OUT, 0.0042, 0.0026) * 0.9)

    img = img.reshape(n, SS, n, SS, 3).mean(axis=(1, 3))     # דאון-סמפלינג
    return (np.clip(img, 0, 1) * 255).round().astype(np.uint8)


def write_png(path, arr):
    n = arr.shape[0]
    raw = b"".join(b"\x00" + arr[i].tobytes() for i in range(n))
    def ch(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    open(path, "wb").write(
        b"\x89PNG\r\n\x1a\n"
        + ch(b"IHDR", struct.pack(">IIBBBBB", n, n, 8, 2, 0, 0, 0))
        + ch(b"IDAT", zlib.compress(raw, 9))
        + ch(b"IEND", b"")
    )
    return len(open(path, "rb").read())


for name, size in [("icon-512.png", 512), ("icon-192.png", 192), ("apple-touch-icon.png", 180)]:
    print(f"  web/icons/{name}: {write_png('web/icons/'+name, render(size)):,} bytes")

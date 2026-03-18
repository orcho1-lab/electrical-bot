"""
bulk_extract.py — חילוץ PDFs ב-0 טוקנים

איך זה עובד:
  - PyMuPDF בלבד לחילוץ טקסט (אין Gemini Vision)
  - Regex לפיצול שאלות לפי מספרים (שאלה 1 / Question 1 / א. וכו')
  - שליחה ל-Cloud Run עם solution="לא פתור" → השרת לא קורא ל-Gemini
  - topic מזוהה עם מילות מפתח מקומיות (ללא Gemini)
  סה"כ: 0 קריאות Gemini

הפעלה:
    py -3.12 scripts/bulk_extract.py
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ── הגדרות ─────────────────────────────────────────────
CLOUD_URL   = "https://electrical-bot-642154412078.europe-west1.run.app"
PASSWORD    = "mahat2025"
LOCAL_EXAMS = Path(__file__).parent.parent / "local_exams"
SKIP_KEYWORDS = ["נוסחאון", "הרצאה", "מצגת", "הסברים"]
SLEEP_SEC   = 0.5   # בין בקשות API
MIN_Q_LEN   = 40    # תווים מינימום לשאלה תקפה
# ───────────────────────────────────────────────────────

try:
    import fitz
except ImportError:
    sys.exit("❌ חסר pymupdf — pip install pymupdf")


# ── זיהוי נושא לפי מילות מפתח (ללא Gemini) ────────────

_TOPIC_MAP = [
    # מכונות חשמל
    ("שנאים",              ["שנאי", "שנאים", "transformer", "turns ratio", "העמסת שנאים"]),
    ("מנוע אסינכרוני",     ["אסינכרוני", "induction", "slip", "היחלקות"]),
    ("גנרטור סינכרוני",    ["גנרטור סינכרוני", "synchronous generator", "מחולל"]),
    ("מנוע סינכרוני",      ["מנוע סינכרוני", "synchronous motor"]),
    ("מנוע DC",            ["מנוע DC", "dc motor", "ארמטורה", "armature"]),
    ("גנרטור DC",          ["גנרטור DC", "dc generator"]),
    ("הנעה חשמלית",        ["הנעה חשמלית", "electric drive", "VFD", "chopper"]),
    # מערכות הספק
    ("שיפור מקדם הספק",    ["מקדם הספק", "power factor", "קבלים", "שיפור"]),
    ("תאורה",              ["תאורה", "גוף תאורה", "נורה", "תאורת פנים", "תאורת חוץ"]),
    ("רשת חלוקה",          ["רשת", "רדיאלי", "טבעתית", "מינימום חומר", "חלוקה"]),
    ("נקודת האפס",         ["נקודת האפס", "נקודת אפס", "מוליך אפס", "זינה צפה"]),
    ("העמסת שנאים",        ["העמסת שנאים", "עומס שנאי", "העמסה"]),
    # מתקני חשמל
    ("הגנה והארקות",       ["הארקה", "חשמול", "TN", "TT", "RCD", "מפסק פחת", "הגנה מפני"]),
    ("כבלים והגנה",        ["כבל", "כבלים", "חתך", "מוליך", "מפסק", "נתיך"]),
]

def classify_topic(text: str) -> str:
    t = text.lower()
    for topic, keywords in _TOPIC_MAP:
        if any(kw.lower() in t for kw in keywords):
            return topic
    return "כללי"


# ── פיצול שאלות מטקסט גולמי ────────────────────────────

_Q_SPLIT = re.compile(
    r'(?:^|\n)\s*(?:'
    r'שאלה\s*\d+'            # שאלה 1
    r'|שאלה\s+[אבגד]'        # שאלה א
    r'|[Qq]uestion\s*\d+'    # Question 1
    r'|\bq\s*\d+\b'          # Q1
    r'|^\d+[\.\)]\s'         # 1. / 1)
    r'|^[אבגדהוזחט][\.\)]\s' # א. / א)
    r')',
    re.MULTILINE | re.IGNORECASE,
)

def split_questions(text: str) -> list[str]:
    """פיצול טקסט לשאלות לפי כותרות שאלה."""
    parts = _Q_SPLIT.split(text)
    result = []
    for part in parts:
        part = part.strip()
        if len(part) >= MIN_Q_LEN:
            result.append(part)
    return result


def extract_pdf_text(pdf_path: Path) -> str:
    """PyMuPDF — כל הטקסט מה-PDF."""
    doc = fitz.open(str(pdf_path))
    pages = []
    for i, page in enumerate(doc):
        t = page.get_text().strip()
        if t:
            pages.append(f"[עמוד {i+1}]\n{t}")
    doc.close()
    return "\n\n".join(pages)


# ── Cloud API ───────────────────────────────────────────

def api_call(path: str, payload: dict | None, token: str | None) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{CLOUD_URL}{path}", data=data, headers=headers,
        method="POST" if data else "GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"    ❌ HTTP {e.code}: {e.read().decode(errors='replace')[:150]}")
        return {}
    except Exception as e:
        print(f"    ❌ שגיאה: {e}")
        return {}


# ── Main ────────────────────────────────────────────────

def main():
    print("🔐 מתחבר...")
    r = api_call("/api/auth/login", {"password": PASSWORD}, None)
    token = r.get("token")
    if not token:
        sys.exit(f"❌ Login נכשל: {r}")
    print("✅ מחובר (JWT)\n")

    files = sorted(
        f for f in LOCAL_EXAMS.iterdir()
        if f.suffix.lower() == ".pdf" and not any(kw in f.name for kw in SKIP_KEYWORDS)
    )

    print(f"📂 {len(files)} קבצים:")
    for f in files:
        print(f"  • {f.name}")
    print()

    total_saved = total_dupes = total_skip = 0

    for pdf in files:
        print(f"━━━ {pdf.name} ━━━")
        raw_text = extract_pdf_text(pdf)
        if not raw_text.strip():
            print("  ⚠️  אין טקסט בקובץ (PDF סרוק בלבד — דרוש Gemini Vision)\n")
            total_skip += 1
            continue

        questions = split_questions(raw_text)
        print(f"  📋 {len(questions)} שאלות זוהו")

        saved = dupes = 0
        for q_text in questions:
            topic = classify_topic(q_text)
            payload = {
                "text": q_text,
                "topic": topic,
                "source": pdf.name,
                "solution": "לא פתור",   # non-empty → שרת לא קורא Gemini לפתרון
                "image_url": "",
            }
            res = api_call("/api/questions", payload, token)
            status = res.get("status", "")
            if status == "saved":
                saved += 1
                print(f"  💾 [{topic}] {q_text[:65].replace(chr(10),' ')}")
            elif status == "duplicate":
                dupes += 1
            time.sleep(SLEEP_SEC)

        total_saved += saved
        total_dupes += dupes
        print(f"  → נשמרו: {saved}  כפולים: {dupes}\n")

    print("=" * 60)
    print(f"🏁 סיכום:")
    print(f"   ✅ נשמרו:   {total_saved}")
    print(f"   🔁 כפולים:  {total_dupes}")
    if total_skip:
        print(f"   ⚠️  דולגו (סרוקים): {total_skip}")
    print(f"\n🌐 {CLOUD_URL}")
    print("=" * 60)


if __name__ == "__main__":
    main()

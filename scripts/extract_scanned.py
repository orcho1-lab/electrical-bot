"""
extract_scanned.py — חילוץ PDFs סרוקים (תמונות) עם Gemini Vision

קבצים לחילוץ:
  - 12032026 1217.pdf
  - CamScanner 16.26 16.2.2026.pdf
  - מכונות חשמל - פתרון מבחן סמסטר א מועד א - 360969_13364.pdf
  - פתרון מבחן אמצע 1.pdf

הפעלה:
    py -3.12 scripts/extract_scanned.py
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
SLEEP_SEC   = 1.5
MIN_Q_LEN   = 30

SCANNED_FILES = [
    "12032026 1217.pdf",
    "CamScanner 16.26 16.2.2026.pdf",
    "מכונות חשמל - פתרון מבחן סמסטר א מועד א - 360969_13364.pdf",
    "פתרון מבחן אמצע 1 .pdf",
]
# ───────────────────────────────────────────────────────

try:
    import fitz
except ImportError:
    sys.exit("❌ חסר pymupdf — pip install pymupdf")

try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
    KEY = os.environ.get("GEMINI_API_KEY", "")
    if not KEY:
        sys.exit("❌ חסר GEMINI_API_KEY ב-.env")
    genai.configure(api_key=KEY)
    vision_model = genai.GenerativeModel("gemini-2.0-flash")
except ImportError:
    sys.exit("❌ חסר google-generativeai")

_TOPIC_MAP = [
    ("שנאי",           ["שנאי", "שנאים", "transformer", "turns ratio"]),
    ("מנוע אסינכרוני", ["אסינכרוני", "induction", "slip", "היחלקות"]),
    ("גנרטור סינכרוני",["גנרטור", "synchronous", "סינכרוני", "power angle"]),
    ("מנוע סינכרוני",  ["מנוע סינכרוני", "synchronous motor"]),
    ("מנוע DC",        ["מנוע DC", "dc motor", "ארמטורה", "armature"]),
    ("גנרטור DC",      ["גנרטור DC", "dc generator"]),
    ("הנעה חשמלית",    ["הנעה", "electric drive", "VFD", "chopper"]),
]

def classify_topic(text: str) -> str:
    t = text.lower()
    for topic, kws in _TOPIC_MAP:
        if any(k.lower() in t for k in kws):
            return topic
    return "כללי"


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
        print(f"    ❌ {e}")
        return {}


def vision_extract_page(png_bytes: bytes, page_num: int, is_solution: bool) -> list[dict]:
    """שולח עמוד אחד ל-Gemini Vision, מחלץ שאלות/פתרונות."""
    if is_solution:
        instruction = (
            "זהו עמוד פתרון מבחן. חלץ כל שאלה יחד עם פתרונה המלא.\n"
            "לכל שאלה החזר את הטקסט של השאלה ואת הפתרון המלא.\n"
        )
        fmt = '{"questions": [{"text": "טקסט השאלה", "solution": "הפתרון המלא", "topic": "נושא"}, ...]}'
    else:
        instruction = (
            "חלץ את כל שאלות/תרגילי מכונות חשמל מעמוד זה.\n"
            "לכל שאלה: תיאור מלא כולל כל הנתונים המספריים.\n"
            "אם יש סרטוט — תאר את המעגל בקצרה.\n"
        )
        fmt = '{"questions": [{"text": "תיאור מלא כולל נתונים", "topic": "נושא"}, ...]}'

    prompt = (
        f"{instruction}"
        "אם העמוד לא מכיל שאלות (כותרת, הוראות, נוסחאון) — החזר רשימה ריקה.\n"
        f"החזר JSON בלבד (ללא ```):\n{fmt}\n"
        'אם אין שאלות: {"questions": []}'
    )

    parts = [{"mime_type": "image/png", "data": png_bytes}, prompt]
    for attempt in range(3):
        try:
            resp = vision_model.generate_content(parts)
            raw = resp.text.strip()
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            return json.loads(match.group()).get("questions", []) if match else []
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                wait = 30 * (attempt + 1)
                print(f"    ⏳ rate-limit, מחכה {wait}s...")
                time.sleep(wait)
            else:
                print(f"    ⚠️  Vision שגיאה עמ' {page_num}: {e}")
                return []
    return []


def process_pdf(pdf_path: Path, is_solution: bool) -> list[dict]:
    doc = fitz.open(str(pdf_path))
    all_questions = []
    print(f"  📖 {len(doc)} עמודים")
    for i in range(len(doc)):
        page = doc[i]
        zoom = 200 / 72
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        png_bytes = pix.tobytes("png")
        qs = vision_extract_page(png_bytes, i + 1, is_solution)
        if qs:
            print(f"    עמ' {i+1}: {len(qs)} שאלות")
        all_questions.extend(qs)
        time.sleep(1)  # בין עמודים
    doc.close()
    return all_questions


def main():
    print("🔐 מתחבר...")
    r = api_call("/api/auth/login", {"password": PASSWORD}, None)
    token = r.get("token")
    if not token:
        sys.exit(f"❌ Login נכשל: {r}")
    print("✅ מחובר\n")

    total_saved = total_dupes = 0

    for fname in SCANNED_FILES:
        # מצא את הקובץ (גם עם רווחים/תווים מיוחדים)
        matches = [f for f in LOCAL_EXAMS.iterdir()
                   if fname.strip() in f.name or f.name.strip() == fname.strip()]
        if not matches:
            # חיפוש גמיש יותר
            base = fname.replace(".pdf","").replace(".PDF","").strip()[:20]
            matches = [f for f in LOCAL_EXAMS.iterdir() if base in f.name]

        if not matches:
            print(f"⚠️  לא נמצא: {fname}")
            continue

        pdf_path = matches[0]
        is_sol = any(kw in pdf_path.name for kw in ["פתרון", "solution"])
        print(f"━━━ {pdf_path.name} {'[פתרון]' if is_sol else '[מבחן]'} ━━━")

        questions = process_pdf(pdf_path, is_solution=is_sol)
        print(f"  📋 סה\"כ {len(questions)} שאלות חולצו")

        saved = dupes = 0
        for q in questions:
            text = (q.get("text","") if isinstance(q, dict) else str(q)).strip()
            if not text or len(text) < MIN_Q_LEN:
                continue
            solution = q.get("solution","") if isinstance(q, dict) else ""
            topic = classify_topic(text)

            payload = {
                "text": text,
                "topic": topic,
                "source": pdf_path.name,
                "solution": solution if solution else "לא פתור",
                "image_url": "",
            }
            res = api_call("/api/questions", payload, token)
            status = res.get("status","")
            if status == "saved":
                saved += 1
                print(f"  💾 [{topic}] {text[:65].replace(chr(10),' ')}")
            elif status == "duplicate":
                dupes += 1
            time.sleep(SLEEP_SEC)

        total_saved += saved
        total_dupes += dupes
        print(f"  → נשמרו: {saved}  כפולים: {dupes}\n")

    print("=" * 60)
    print(f"🏁 סיכום:")
    print(f"   ✅ נשמרו:  {total_saved}")
    print(f"   🔁 כפולים: {total_dupes}")
    print(f"\n🌐 {CLOUD_URL}")
    print("=" * 60)


if __name__ == "__main__":
    main()

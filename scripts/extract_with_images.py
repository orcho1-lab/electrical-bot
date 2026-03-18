"""
extract_with_images.py — חילוץ PDFs סרוקים עם שמירת תמונות ב-GCS

לכל עמוד PDF:
  1. ממיר לתמונה PNG (PyMuPDF)
  2. שולח ל-/api/questions/extract-image
  3. השרת: שומר תמונה ל-GCS + Gemini Vision + שמירה ל-DB עם image_url

הפעלה:
    py -3.12 scripts/extract_with_images.py
"""

import base64, json, sys, time, urllib.request, urllib.error
from pathlib import Path

CLOUD_URL   = "https://electrical-bot-642154412078.europe-west1.run.app"
PASSWORD    = "mahat2025"
LOCAL_EXAMS = Path(__file__).parent.parent / "local_exams"
SLEEP_PAGES = 2   # שניות בין עמודים
SLEEP_FILES = 3   # שניות בין קבצים

# קבצים סרוקים בלבד (ללא טקסט)
SCANNED_FILES = [
    "12032026 1217.pdf",
    "CamScanner 16.26 16.2.2026.pdf",
    "מכונות חשמל - פתרון מבחן סמסטר א מועד א - 360969_13364.pdf",
    "פתרון מבחן אמצע 1 .pdf",
    "פתרון מערכות הספק 26.2.26.pdf",
    "פתרון מערכות הספק 8.2 .pdf",
]

try:
    import fitz
except ImportError:
    sys.exit("❌ חסר pymupdf — pip install pymupdf")


def api(path: str, payload: dict, token: str) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {token}",
    }
    req = urllib.request.Request(f"{CLOUD_URL}{path}", data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"    ❌ HTTP {e.code}: {body[:150]}")
        return {}
    except Exception as e:
        print(f"    ❌ {e}")
        return {}


def main():
    # Login
    req = urllib.request.Request(f"{CLOUD_URL}/api/auth/login",
        data=json.dumps({"password": PASSWORD}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        token = json.loads(r.read())["token"]
    print("✅ מחובר\n")

    total_saved = total_dupes = 0

    for fname in SCANNED_FILES:
        # מצא קובץ (גם עם תווים מיוחדים)
        matches = [f for f in LOCAL_EXAMS.iterdir()
                   if f.name.strip() == fname.strip() or
                      fname.strip().replace(".pdf","") in f.name]
        if not matches:
            print(f"⚠️  לא נמצא: {fname}")
            continue

        pdf_path = matches[0]
        doc = fitz.open(str(pdf_path))
        print(f"━━━ {pdf_path.name} ({len(doc)} עמודים) ━━━")

        saved = dupes = 0
        for i in range(len(doc)):
            page = doc[i]
            zoom = 200 / 72
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            png_bytes = pix.tobytes("png")
            b64 = base64.b64encode(png_bytes).decode()

            print(f"  עמ' {i+1}/{len(doc)} ", end="", flush=True)
            res = api("/api/questions/extract-image", {
                "message": pdf_path.name,
                "image_data": b64,
                "image_mime_type": "image/png",
            }, token)

            s = res.get("saved", 0)
            d = res.get("duplicates", 0)
            e = res.get("extracted", 0)
            url = res.get("image_url", "")
            saved += s
            dupes += d
            print(f"→ {e} חולצו, {s} נשמרו, {d} כפולים {'🖼️' if url else ''}")
            time.sleep(SLEEP_PAGES)

        doc.close()
        total_saved += saved
        total_dupes += dupes
        print(f"  סיכום: {saved} נשמרו, {dupes} כפולים\n")
        time.sleep(SLEEP_FILES)

    print("=" * 60)
    print(f"🏁 סיכום כולל:")
    print(f"   ✅ נשמרו עם תמונות: {total_saved}")
    print(f"   🔁 כפולים:          {total_dupes}")
    print(f"\n🌐 {CLOUD_URL}")
    print("=" * 60)


if __name__ == "__main__":
    main()

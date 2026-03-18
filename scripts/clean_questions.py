"""
clean_questions.py — תיקון טקסט שאלות: שבירות שורה, מספרים מפוצלים, מילים חתוכות
"""
import json, re, sys, urllib.request

URL = "https://electrical-bot-642154412078.europe-west1.run.app"

# Login
req = urllib.request.Request(f"{URL}/api/auth/login",
    data=json.dumps({"password":"mahat2025"}).encode(),
    headers={"Content-Type":"application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=10) as r:
    token = json.loads(r.read())["token"]

HDR = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}

# Fetch
req = urllib.request.Request(f"{URL}/api/questions", headers={"Authorization": f"Bearer {token}"})
with urllib.request.urlopen(req, timeout=10) as r:
    data = json.loads(r.read())


def clean(text: str) -> str:
    # 1. שבירת שורה בתוך מספר עשרוני: "28. \n8°" → "28.8°"
    text = re.sub(r'(\d+)\.\s*\n\s*(\d)', r'\1.\2', text)
    # 2. שבירת שורה בתוך מספר: "343. \n66" → "343.66"
    text = re.sub(r'(\d)\s*\n\s*(\d)', r'\1\2', text)
    # 3. מילה עברית חתוכה בשורה: שורה מסתיימת באות עברית + שורה הבאה מתחילה באות עברית → חיבור
    text = re.sub(r'([\u05D0-\u05EA])\n([\u05D0-\u05EA])', r'\1\2', text)
    # 4. רווח + שבירת שורה + המשך הצמד → כמו "הע \nמס" → "העומס"
    text = re.sub(r'([\u05D0-\u05EA]) \n([\u05D0-\u05EA])', r'\1\2', text)
    # 5. רווחים כפולים לפני/אחרי ספרות (מ-PDF)  "28. 8" → "28.8"
    text = re.sub(r'(\d)\. (\d)', r'\1.\2', text)
    # 6. שלוש+ שבירות שורה → שתיים
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 7. ניקוי סופי
    return text.strip()


fixed = 0
for q in data:
    txt = q.get("text", "") or ""
    cleaned = clean(txt)
    if cleaned != txt:
        payload = json.dumps({"text": cleaned}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(f"{URL}/api/questions/{q['id']}",
            data=payload, method="PUT", headers=HDR)
        try:
            urllib.request.urlopen(req, timeout=10)
            fixed += 1
            print(f"✓ [{q['id']}] {cleaned[:80]}")
        except Exception as e:
            print(f"✗ {q['id']}: {e}")

print(f"\n✅ תוקנו: {fixed} | סה\"כ: {len(data)}")

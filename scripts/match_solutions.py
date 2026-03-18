"""
match_solutions.py — שיוך פתרונות לשאלות ע"י Gemini

לוגיקה:
  1. מושך את כל השאלות מה-API
  2. מפריד: unsolved (לא פתור) vs solved (יש פתרון אמיתי)
  3. מקבץ לפי נושא כדי לצמצם מספר השוואות
  4. Gemini בוחן כל קבוצה ומחזיר זוגות שאלה-פתרון
  5. PUT לכל שיוך בטוח (confidence >= 0.8)

הפעלה:
    py -3.12 scripts/match_solutions.py

עלות: ~1 קריאת Gemini לכל נושא שיש בו גם שאלות וגם פתרונות
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

# ── הגדרות ──────────────────────────────────────────────
CLOUD_URL  = "https://electrical-bot-642154412078.europe-west1.run.app"
PASSWORD   = "mahat2025"
CONFIDENCE = 0.75        # סף מינימלי לשיוך
SLEEP_SEC  = 1.5         # בין קריאות Gemini
# ────────────────────────────────────────────────────────

load_dotenv(Path(__file__).parent.parent / ".env")
KEY = os.environ.get("GEMINI_API_KEY", "")
if not KEY:
    sys.exit("❌ חסר GEMINI_API_KEY ב-.env")

try:
    import google.generativeai as genai
    genai.configure(api_key=KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
except ImportError:
    sys.exit("❌ pip install google-generativeai")


# ── API helpers ──────────────────────────────────────────

def api(path: str, method: str = "GET", payload: dict | None = None, token: str | None = None) -> dict | list:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{CLOUD_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  ❌ HTTP {e.code}: {e.read().decode(errors='replace')[:200]}")
        return {}
    except Exception as e:
        print(f"  ❌ {e}")
        return {}


def login() -> str:
    r = api("/api/auth/login", "POST", {"password": PASSWORD})
    token = r.get("token") if isinstance(r, dict) else None
    if not token:
        sys.exit(f"❌ Login נכשל: {r}")
    return token


# ── Gemini matching ──────────────────────────────────────

def gemini_match(unsolved: list[dict], solved: list[dict]) -> list[dict]:
    """
    שולח קבוצה של שאלות לא פתורות + פתרונות ל-Gemini.
    מחזיר רשימה של { question_id, solution_id, confidence, reason }
    """
    if not unsolved or not solved:
        return []

    q_block = "\n\n".join(
        f"[שאלה {q['id']}] נושא={q.get('topic','')}\n{q['text'][:400]}"
        for q in unsolved
    )
    s_block = "\n\n".join(
        f"[פתרון {s['id']}] נושא={s.get('topic','')}\n{s['solution'][:500]}"
        for s in solved
    )

    prompt = f"""
להלן שאלות ללא פתרון ופתרונות שנחלצו מ-PDFs שונים.
תפקידך: לשייך כל פתרון לשאלה שלו לפי התוכן (נתונים, ערכים מספריים, נושא).

שאלות:
{q_block}

פתרונות:
{s_block}

החזר JSON בלבד (ללא ```) בפורמט:
{{
  "matches": [
    {{"question_id": <int>, "solution_id": <int>, "confidence": <0.0-1.0>, "reason": "הסבר קצר"}}
  ]
}}

כללים:
- שייך רק אם אתה בטוח — confidence >= 0.8
- פתרון אחד לשאלה אחת בלבד
- אם אין התאמה בטוחה — אל תשייך
- אם הפתרון כולל שאלה בתוכו — השתמש בטקסט השאלה לאימות

אם אין שיוכים בטוחים: {{"matches": []}}
"""

    for attempt in range(3):
        try:
            resp = model.generate_content(prompt)
            raw = resp.text.strip()
            # נקה ```json``` אם קיים
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            import re
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if not m:
                return []
            data = json.loads(m.group())
            return data.get("matches", [])
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                wait = 60 * (attempt + 1)
                print(f"  ⏳ rate-limit, מחכה {wait}s...")
                time.sleep(wait)
            else:
                print(f"  ⚠️  Gemini שגיאה: {e}")
                return []
    return []


# ── Main ─────────────────────────────────────────────────

def has_solution(q: dict) -> bool:
    sol = (q.get("solution") or "").strip()
    return bool(sol and sol != "לא פתור" and len(sol) > 10)


def main():
    print("🔐 מתחבר...")
    token = login()
    print("✅ מחובר\n")

    # טען את כל השאלות
    print("📥 טוען שאלות...")
    questions = api("/api/questions", token=token)
    if not isinstance(questions, list):
        sys.exit(f"❌ שגיאה בטעינת שאלות: {questions}")
    print(f"  סה\"כ: {len(questions)} שאלות")

    unsolved = [q for q in questions if not has_solution(q)]
    solved   = [q for q in questions if has_solution(q)]
    print(f"  📝 ללא פתרון: {len(unsolved)}")
    print(f"  ✅ עם פתרון:  {len(solved)}\n")

    if not unsolved or not solved:
        print("אין מה לשייך.")
        return

    # קבץ לפי נושא (פחות קריאות Gemini)
    topics = set(q.get("topic", "כללי") for q in unsolved)
    total_matched = 0

    for topic in sorted(topics):
        u_group = [q for q in unsolved  if q.get("topic", "כללי") == topic]
        s_group = [q for q in solved    if q.get("topic", "כללי") == topic]

        if not u_group or not s_group:
            continue

        print(f"━━━ {topic}: {len(u_group)} שאלות, {len(s_group)} פתרונות ━━━")

        # פצל לקבוצות של עד 8×8 כדי לא לחרוג מ-context
        CHUNK = 8
        for i in range(0, len(u_group), CHUNK):
            for j in range(0, len(s_group), CHUNK):
                u_chunk = u_group[i:i+CHUNK]
                s_chunk = s_group[j:j+CHUNK]

                matches = gemini_match(u_chunk, s_chunk)
                if not matches:
                    time.sleep(SLEEP_SEC)
                    continue

                for m in matches:
                    qid  = m.get("question_id")
                    sid  = m.get("solution_id")
                    conf = float(m.get("confidence", 0))
                    reason = m.get("reason", "")

                    if conf < CONFIDENCE:
                        print(f"  ⚠️  שאלה {qid} ← פתרון {sid}: confidence {conf:.2f} — דולג")
                        continue

                    # מצא את טקסט הפתרון
                    sol_q = next((q for q in solved if q["id"] == sid), None)
                    if not sol_q:
                        continue

                    solution_text = sol_q["solution"]

                    # עדכן בDB
                    result = api(f"/api/questions/{qid}", "PUT",
                                 {"solution": solution_text}, token)
                    if isinstance(result, dict) and result.get("id"):
                        print(f"  ✅ שאלה {qid} ← פתרון {sid} (conf={conf:.2f}) — {reason[:60]}")
                        total_matched += 1
                    else:
                        print(f"  ❌ עדכון נכשל: שאלה {qid} ← {result}")

                time.sleep(SLEEP_SEC)

    print("\n" + "=" * 60)
    print(f"🏁 סיכום: {total_matched} שיוכים בוצעו")
    print("=" * 60)


if __name__ == "__main__":
    main()

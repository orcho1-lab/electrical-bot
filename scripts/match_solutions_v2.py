"""
match_solutions_v2.py — שיוך חד-חד-ערכי: פתרון אחד לשאלה אחת

שיפורים על v1:
  - אוסף את כל ההתאמות תחילה (ללא PUT)
  - dedup לפי question_id: שומר רק confidence מקסימלי
  - dedup לפי solution_id: שומר רק confidence מקסימלי (פתרון לא יינתן לשתי שאלות)
  - PUT רק אחרי הסינון
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

CLOUD_URL  = "https://electrical-bot-642154412078.europe-west1.run.app"
PASSWORD   = "mahat2025"
CONFIDENCE = 0.85        # סף מחמיר יותר מ-v1
SLEEP_SEC  = 1.5

load_dotenv(Path(__file__).parent.parent / ".env")
KEY = os.environ.get("GEMINI_API_KEY", "")
if not KEY:
    sys.exit("❌ חסר GEMINI_API_KEY")

try:
    import google.generativeai as genai
    genai.configure(api_key=KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
except ImportError:
    sys.exit("❌ pip install google-generativeai")


# ── API ──────────────────────────────────────────────────

def api(path, method="GET", payload=None, token=None):
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


def login():
    r = api("/api/auth/login", "POST", {"password": PASSWORD})
    t = r.get("token") if isinstance(r, dict) else None
    if not t:
        sys.exit(f"❌ Login: {r}")
    return t


# ── Gemini ───────────────────────────────────────────────

def gemini_match(unsolved: list[dict], solved: list[dict]) -> list[dict]:
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
שייך כל פתרון לשאלה שלו לפי: ערכים מספריים זהים, נתונים משותפים, תוצאה זהה.

חשוב ביותר:
- כל פתרון שייך לשאלה אחת בלבד
- כל שאלה מקבלת לכל היותר פתרון אחד
- אם הפתרון כללי ולא ספציפי לשאלה — confidence נמוך מ-0.85

שאלות:
{q_block}

פתרונות:
{s_block}

החזר JSON בלבד (ללא ```):
{{"matches": [{{"question_id": <int>, "solution_id": <int>, "confidence": <0-1>, "reason": "..."}}]}}

אם אין שיוך בטוח (confidence >= 0.85): {{"matches": []}}
"""
    for attempt in range(3):
        try:
            resp = model.generate_content(prompt)
            raw = resp.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            import re
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if not m:
                return []
            return json.loads(m.group()).get("matches", [])
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                wait = 60 * (attempt + 1)
                print(f"  ⏳ rate-limit, מחכה {wait}s...")
                time.sleep(wait)
            else:
                print(f"  ⚠️  {e}")
                return []
    return []


# ── Dedup ────────────────────────────────────────────────

def deduplicate(all_matches: list[dict], solved_by_id: dict) -> list[dict]:
    """
    שומר רק את ההתאמה הטובה ביותר לכל שאלה ולכל פתרון.
    """
    # question_id → (confidence, match)
    best_by_q: dict[int, tuple[float, dict]] = {}
    # solution_id → (confidence, match)
    best_by_s: dict[int, tuple[float, dict]] = {}

    for m in all_matches:
        qid  = m["question_id"]
        sid  = m["solution_id"]
        conf = float(m.get("confidence", 0))

        # בחר הטוב ביותר לפי שאלה
        if qid not in best_by_q or conf > best_by_q[qid][0]:
            best_by_q[qid] = (conf, m)

    # עכשיו מתוך הטובים לפי שאלה — בחר טוב לפי פתרון
    candidates = [v[1] for v in best_by_q.values()]
    final: list[dict] = []
    for m in sorted(candidates, key=lambda x: -x.get("confidence", 0)):
        sid = m["solution_id"]
        if sid not in best_by_s:
            best_by_s[sid] = (m.get("confidence", 0), m)
            final.append(m)
        # אחרת: הפתרון כבר שויך לשאלה אחרת עם confidence גבוה יותר

    return final


# ── Main ─────────────────────────────────────────────────

_BOT_PHRASES = [
    "בטח, אני אעזור",
    "בסדר, אני אעזור",
    "שלום! אני שמח לעזור",
    "בטח! אני אעזור",
    "אני כאן כדי ללוות",
    "אני אפתור את התרגיל",
    "שלום! בשמחה רבה",
]

def is_bot_generated(sol: str) -> bool:
    """פתרון שנוצר ע"י הבוט בזמן צ'אט — לא מ-PDF"""
    for phrase in _BOT_PHRASES:
        if sol.startswith(phrase) or phrase in sol[:80]:
            return True
    return False

def has_real_solution(q):
    """פתרון אמיתי שחולץ מ-PDF (לא תשובת בוט)"""
    sol = (q.get("solution") or "").strip()
    if not sol or sol == "לא פתור" or len(sol) < 10:
        return False
    return not is_bot_generated(sol)

def has_solution(q):
    sol = (q.get("solution") or "").strip()
    return bool(sol and sol != "לא פתור" and len(sol) > 10)


def main():
    print("🔐 מתחבר...")
    token = login()
    print("✅ מחובר\n")

    print("📥 טוען שאלות...")
    questions = api("/api/questions", token=token)
    if not isinstance(questions, list):
        sys.exit(f"❌ {questions}")
    print(f"  סה\"כ: {len(questions)} שאלות")

    unsolved = [q for q in questions if not has_solution(q)]
    solved   = [q for q in questions if has_real_solution(q)]   # רק מ-PDF!
    bot_sols = [q for q in questions if has_solution(q) and not has_real_solution(q)]
    solved_by_id = {q["id"]: q for q in solved}

    print(f"  📝 ללא פתרון:         {len(unsolved)}")
    print(f"  ✅ פתרון מ-PDF:        {len(solved)}")
    print(f"  🤖 פתרון בוט (מדולג): {len(bot_sols)}\n")

    if not unsolved or not solved:
        print("אין מה לשייך.")
        return

    # שלב א: אסוף את כל ההתאמות (ללא PUT)
    print("🔍 שלב א — איסוף התאמות מ-Gemini...\n")
    all_matches: list[dict] = []
    topics = set(q.get("topic", "כללי") for q in unsolved)

    CHUNK = 8
    for topic in sorted(topics):
        u_group = [q for q in unsolved if q.get("topic", "כללי") == topic]
        s_group = [q for q in solved   if q.get("topic", "כללי") == topic]
        if not u_group or not s_group:
            continue

        print(f"━━━ {topic}: {len(u_group)} שאלות, {len(s_group)} פתרונות")
        for i in range(0, len(u_group), CHUNK):
            for j in range(0, len(s_group), CHUNK):
                matches = gemini_match(u_group[i:i+CHUNK], s_group[j:j+CHUNK])
                filtered = [m for m in matches if float(m.get("confidence", 0)) >= CONFIDENCE]
                all_matches.extend(filtered)
                if filtered:
                    print(f"  +{len(filtered)} התאמות (chunk {i//CHUNK},{j//CHUNK})")
                time.sleep(SLEEP_SEC)

    print(f"\n  📊 סה\"כ לפני dedup: {len(all_matches)} התאמות")

    # שלב ב: dedup
    final_matches = deduplicate(all_matches, solved_by_id)
    print(f"  ✂️  אחרי dedup: {len(final_matches)} התאמות חד-חד-ערכיות\n")

    # שלב ג: PUT
    print("💾 שלב ב — שמירה ב-DB...\n")
    done = 0
    for m in sorted(final_matches, key=lambda x: x["question_id"]):
        qid  = m["question_id"]
        sid  = m["solution_id"]
        conf = m.get("confidence", 0)
        sol_q = solved_by_id.get(sid)
        if not sol_q:
            continue
        r = api(f"/api/questions/{qid}", "PUT",
                {"solution": sol_q["solution"]}, token)
        if isinstance(r, dict) and r.get("id"):
            print(f"  ✅ שאלה {qid} ← פתרון {sid} (conf={conf:.2f})")
            done += 1
        else:
            print(f"  ❌ שאלה {qid}: {r}")

    print(f"\n{'='*60}")
    print(f"🏁 סיכום: {done} שיוכים נשמרו (חד-חד-ערכי)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

"""
match_solutions_v3.py — שיוך פתרון מ"שאלות-פתרון" לשאלות אמיתיות

הבעיה: PDFים של "פתרון מבחן..." חולצו כשאלות — ה-text שלהן הוא הפתרון.
הפתרון: זיהוי מקורות-פתרון ← שימוש ב-text שלהם כפתרון לשאלות המתאימות.

זוגות ידועים (לפי תאריך/שם):
  מבחן סוף 2 סמסטר א 26.2.26  ↔ פתרון מערכות הספק 26.2.26
  מבחן סוף סמסטר א ב1 8.2.26  ↔ פתרון מערכות הספק 8.2
  [מכונות - כל מקורות]         ↔ מכונות חשמל - פתרון מבחן סמסטר א
  [מכונות - תרגילים]           ↔ מתקני חשמל ב' - פתרונות
"""

import json, os, sys, time, re
import urllib.request, urllib.error
from pathlib import Path
from dotenv import load_dotenv

CLOUD_URL  = "https://electrical-bot-642154412078.europe-west1.run.app"
PASSWORD   = "mahat2025"
CONFIDENCE = 0.85
SLEEP_SEC  = 1.5
CHUNK      = 6  # שאלות לקריאת Gemini

# זוגות מקור-שאלה ↔ מקור-פתרון (מחרוזות חלקיות)
PAIRS = [
    ("מבחן סוף 2 סמסטר א",       "פתרון מערכות הספק 26.2"),
    ("מבחן סוף סמסטר א ב1",      "פתרון מערכות הספק 8.2"),
    ("מכונות חשמל - תרגילים",    "מכונות חשמל - פתרון מבחן סמסטר א"),
    ("גנרטור (מחולל) סינכרוני",  "מכונות חשמל - פתרון מבחן סמסטר א"),
    ("פתרון מבחן אמצע 1",        "מכונות חשמל - פתרון מבחן סמסטר א"),  # מקור אמצע
    ("מתקני חשמל",               "מתקני חשמל ב' - פתרונות"),
    ("הארקות ואמצעי הגנה",       "מתקני חשמל ב' - פתרונות"),
    ("העמסת שנאיים",             "מערכות הספק ב' - פתרון חלקי"),
    ("גיליון תרגילים",           "מערכות הספק ב' - פתרון חלק 2"),
]

# מקורות שהם בעצם פתרונות (text = פתרון, לא שאלה)
SOLUTION_SOURCES = [
    "פתרון מערכות הספק 26.2",
    "פתרון מערכות הספק 8.2",
    "מכונות חשמל - פתרון מבחן סמסטר א",
    "מתקני חשמל ב' - פתרונות",
    "מערכות הספק ב' - פתרון חלקי",
    "מערכות הספק ב' - פתרון חלק 2",
    "פתרון מבחן אמצע 1",
]

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

def gemini_match(questions: list[dict], sol_entries: list[dict]) -> list[dict]:
    """
    questions  — שאלות אמיתיות (text = השאלה)
    sol_entries — רשומות מקור-פתרון (text = הפתרון)
    מחזיר: [{ question_id, solution_entry_id, confidence, reason }]
    """
    if not questions or not sol_entries:
        return []

    q_block = "\n\n".join(
        f"[שאלה {q['id']}]\n{q['text'][:350]}"
        for q in questions
    )
    s_block = "\n\n".join(
        f"[פתרון {s['id']}]\n{s['text'][:450]}"
        for s in sol_entries
    )

    prompt = f"""
להלן שאלות מבחן ופתרונות שחולצו בנפרד מ-PDF.
תפקידך: לשייך כל פתרון לשאלה שלו לפי ערכים מספריים זהים, נתונים משותפים, ותוצאות.

כללים:
- כל פתרון שייך לשאלה אחת בלבד
- כל שאלה מקבלת לכל היותר פתרון אחד
- confidence >= 0.85 בלבד
- אם הפתרון לא מתאים בוודאות לאף שאלה — אל תשייך

שאלות:
{q_block}

פתרונות:
{s_block}

החזר JSON בלבד (ללא ```):
{{"matches": [{{"question_id": <int>, "solution_entry_id": <int>, "confidence": <0-1>, "reason": "..."}}]}}

אם אין שיוך בטוח: {{"matches": []}}
"""
    for attempt in range(3):
        try:
            resp = model.generate_content(prompt)
            raw = resp.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if not m:
                return []
            return json.loads(m.group()).get("matches", [])
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                wait = 60 * (attempt + 1)
                print(f"  ⏳ rate-limit, {wait}s...")
                time.sleep(wait)
            else:
                print(f"  ⚠️  {e}")
                return []
    return []


# ── Dedup ────────────────────────────────────────────────

def deduplicate(all_matches: list[dict]) -> list[dict]:
    best_by_q: dict[int, tuple[float, dict]] = {}
    for m in all_matches:
        qid  = m["question_id"]
        conf = float(m.get("confidence", 0))
        if qid not in best_by_q or conf > best_by_q[qid][0]:
            best_by_q[qid] = (conf, m)

    # מתוך הטובים לפי שאלה — dedup לפי פתרון
    used_sol: set[int] = set()
    final: list[dict] = []
    for _, m in sorted(best_by_q.values(), key=lambda x: -x[0]):
        sid = m["solution_entry_id"]
        if sid not in used_sol:
            used_sol.add(sid)
            final.append(m)

    return final


# ── Helpers ───────────────────────────────────────────────

def src_match(source: str, patterns: list[str]) -> bool:
    return any(p in (source or "") for p in patterns)

def is_sol_source(source: str) -> bool:
    return src_match(source, SOLUTION_SOURCES)


# ── Main ─────────────────────────────────────────────────

def main():
    print("🔐 מתחבר...")
    token = login()
    print("✅ מחובר\n")

    print("📥 טוען שאלות...")
    questions = api("/api/questions", token=token)
    if not isinstance(questions, list):
        sys.exit(f"❌ {questions}")
    print(f"  סה\"כ: {len(questions)} רשומות")

    # הפרד: שאלות אמיתיות vs רשומות-פתרון
    real_qs  = [q for q in questions if not is_sol_source(q.get("source", ""))]
    sol_ents = [q for q in questions if is_sol_source(q.get("source", ""))]
    print(f"  ❓ שאלות אמיתיות: {len(real_qs)}")
    print(f"  📋 רשומות-פתרון: {len(sol_ents)}")

    # סנן שאלות שכבר יש להן פתרון אמיתי (לא "לא פתור" ולא בוט)
    BOT = ["בטח, אני", "בסדר, אני", "שלום! אני שמח", "בטח! אני",
           "אני כאן כדי", "אני אפתור", "שלום! בשמחה", "בשמחה רבה"]
    def is_bot(s):
        return any(p in (s or "")[:80] for p in BOT)

    def needs_sol(q):
        sol = (q.get("solution") or "").strip()
        return not sol or sol == "לא פתור" or is_bot(sol)

    unsolved_qs = [q for q in real_qs if needs_sol(q)]
    print(f"  📝 ללא פתרון אמיתי: {len(unsolved_qs)}\n")

    sol_by_id = {s["id"]: s for s in sol_ents}

    # עבד לפי זוגות
    all_matches: list[dict] = []

    for q_pat, s_pat in PAIRS:
        q_group = [q for q in unsolved_qs  if q_pat in (q.get("source",""))]
        s_group = [s for s in sol_ents     if s_pat in (s.get("source",""))]

        if not q_group or not s_group:
            continue

        print(f"━━━ {q_pat[:35]} ↔ {s_pat[:35]}")
        print(f"     {len(q_group)} שאלות, {len(s_group)} פתרונות")

        for i in range(0, len(q_group), CHUNK):
            for j in range(0, len(s_group), CHUNK):
                matches = gemini_match(q_group[i:i+CHUNK], s_group[j:j+CHUNK])
                filtered = [m for m in matches if float(m.get("confidence", 0)) >= CONFIDENCE]
                all_matches.extend(filtered)
                if filtered:
                    for m in filtered:
                        print(f"  +match: שאלה {m['question_id']} ← פתרון {m['solution_entry_id']} (conf={m.get('confidence',0):.2f})")
                time.sleep(SLEEP_SEC)

    # גם: כל שאלה אל כל פתרון מאותו נושא (ללא pair)
    # (נושאים שאין להם pair מוגדר)
    paired_q_pats = set(p for p, _ in PAIRS)
    paired_s_pats = set(p for _, p in PAIRS)
    leftover_qs = [q for q in unsolved_qs
                   if not any(p in (q.get("source","")) for p in paired_q_pats)]
    leftover_ss = [s for s in sol_ents
                   if not any(p in (s.get("source","")) for p in paired_s_pats)]

    if leftover_qs and leftover_ss:
        print(f"\n━━━ שאריות: {len(leftover_qs)} שאלות, {len(leftover_ss)} פתרונות")
        topics = set(q.get("topic","כללי") for q in leftover_qs)
        for topic in sorted(topics):
            uq = [q for q in leftover_qs if q.get("topic","כללי") == topic]
            ss = [s for s in leftover_ss if s.get("topic","כללי") == topic]
            if not uq or not ss:
                continue
            print(f"  נושא: {topic}: {len(uq)} שאלות, {len(ss)} פתרונות")
            for i in range(0, len(uq), CHUNK):
                for j in range(0, len(ss), CHUNK):
                    matches = gemini_match(uq[i:i+CHUNK], ss[j:j+CHUNK])
                    filtered = [m for m in matches if float(m.get("confidence",0)) >= CONFIDENCE]
                    all_matches.extend(filtered)
                    if filtered:
                        for m in filtered:
                            print(f"    +match: {m['question_id']} ← {m['solution_entry_id']} (conf={m.get('confidence',0):.2f})")
                    time.sleep(SLEEP_SEC)

    print(f"\n  📊 סה\"כ לפני dedup: {len(all_matches)}")
    final = deduplicate(all_matches)
    print(f"  ✂️  אחרי dedup: {len(final)} חד-חד-ערכי\n")

    # PUT
    print("💾 שומר...")
    done = 0
    for m in sorted(final, key=lambda x: x["question_id"]):
        qid  = m["question_id"]
        sid  = m["solution_entry_id"]
        conf = m.get("confidence", 0)
        sol_entry = sol_by_id.get(sid)
        if not sol_entry:
            continue
        solution_text = sol_entry["text"]  # ← text של רשומת-הפתרון
        r = api(f"/api/questions/{qid}", "PUT",
                {"solution": solution_text}, token)
        if isinstance(r, dict) and r.get("id"):
            print(f"  ✅ שאלה {qid} ← פתרון-entry {sid} (conf={conf:.2f})")
            done += 1
        else:
            print(f"  ❌ שאלה {qid}: {r}")

    print(f"\n{'='*60}")
    print(f"🏁 סיכום: {done} שיוכים נשמרו")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

"""
cleanup_duplicates.py — מנקה שיוכים כפולים

הבעיה: הסקריפט הקודם שייך את אותו פתרון למספר שאלות.
הפתרון:
  1. מושך את כל השאלות
  2. מוצא שאלות שקיבלו את אותו טקסט פתרון
  3. מאפס את כולן חזרה ל"לא פתור"
  (הסקריפט המשופר יבצע שיוך חד-חד-ערכי מחדש)
"""

import json
import os
import sys
import hashlib
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

CLOUD_URL = "https://electrical-bot-642154412078.europe-west1.run.app"
PASSWORD  = "mahat2025"

load_dotenv(Path(__file__).parent.parent / ".env")


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


def login():
    r = api("/api/auth/login", "POST", {"password": PASSWORD})
    token = r.get("token") if isinstance(r, dict) else None
    if not token:
        sys.exit(f"❌ Login נכשל: {r}")
    return token


def sol_key(sol_text: str) -> str:
    """מפתח נורמלי לטקסט פתרון (מסיר רווחים עודפים)"""
    return hashlib.md5(sol_text.strip()[:500].encode("utf-8")).hexdigest()


def main():
    print("🔐 מתחבר...")
    token = login()

    print("📥 טוען שאלות...")
    questions = api("/api/questions", token=token)
    if not isinstance(questions, list):
        sys.exit(f"❌ {questions}")

    print(f"  סה\"כ: {len(questions)} שאלות")

    # מפה: solution_key → רשימת שאלות עם אותו פתרון
    sol_map: dict[str, list[dict]] = {}
    for q in questions:
        sol = (q.get("solution") or "").strip()
        if not sol or sol == "לא פתור" or len(sol) < 20:
            continue
        key = sol_key(sol)
        sol_map.setdefault(key, []).append(q)

    # מצא קבוצות כפולות
    duplicates = {k: qs for k, qs in sol_map.items() if len(qs) > 1}
    print(f"  🔁 קבוצות של פתרון משותף: {len(duplicates)}")

    if not duplicates:
        print("✅ אין כפולים — הכל נקי!")
        return

    total_reset = 0
    for key, group in duplicates.items():
        ids = [q["id"] for q in group]
        snippet = group[0]["solution"][:60].replace("\n", " ")
        print(f"\n  פתרון משותף ל-{len(group)} שאלות {ids}: \"{snippet}...\"")
        # אפס את כולן
        for q in group:
            r = api(f"/api/questions/{q['id']}", "PUT",
                    {"solution": "לא פתור"}, token)
            if isinstance(r, dict) and r.get("id"):
                print(f"    ♻️  שאלה {q['id']} אופסה")
                total_reset += 1
            else:
                print(f"    ❌ שאלה {q['id']}: {r}")

    print(f"\n{'='*60}")
    print(f"🏁 אופסו {total_reset} שאלות — מוכן לשיוך מחדש")
    print(f"{'='*60}")
    print("הפעל עכשיו: py -3.12 scripts/match_solutions_v2.py")


if __name__ == "__main__":
    main()

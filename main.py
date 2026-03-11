import base64
import glob as _glob
import json
import os
import re
import threading
import time
import uuid as _uuid
from typing import Optional

import fitz  # PyMuPDF — PDF → image conversion

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import Database, _normalize_text
from prompts import SYSTEM_PROMPT

load_dotenv()

app = FastAPI(title="Electrical Machines Bot")
db = Database()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY not set. Create a .env file based on .env.example")

genai.configure(api_key=api_key)

MODEL_NAME = "gemini-3.1-pro-preview"
SUMMARY_MODEL_NAME = "gemini-2.0-flash"

# Load official מהט solutions if available
_BASE_DIR = os.path.dirname(__file__) or "."
_MAHAT_TEXTS_DIR = os.path.join(_BASE_DIR, "mahat_texts")
_MAHAT_PDFS_DIR = os.path.join(_BASE_DIR, "mahat_pdfs")

# Exam code → human-readable name
_EXAM_CODES = {
    "90619": "הנדסאים (ישן)",
    "92215": "קירור",
    "93619": "טכנאים",
    "97161": "הנדסאים (חדש)",
    "97163": "טכנאים (חדש)",
}
_SEASONS = {"spring": "אביב", "summer": "קיץ"}

_solutions_text = ""
_SOLUTIONS_FILE = os.path.join(_BASE_DIR, "mahat_solutions_clean.txt")
if os.path.exists(_SOLUTIONS_FILE):
    with open(_SOLUTIONS_FILE, "r", encoding="utf-8") as _f:
        _solutions_text = _f.read()
    print(f"[INIT] Loaded {len(_solutions_text):,} chars of official מהט solutions")

# Load theory knowledge if available
_theory_text = ""
_THEORY_FILE = os.path.join(_BASE_DIR, "mahat_theory_clean.txt")
if os.path.exists(_THEORY_FILE):
    with open(_THEORY_FILE, "r", encoding="utf-8") as _f:
        _theory_text = _f.read()
    print(f"[INIT] Loaded {len(_theory_text):,} chars of theory knowledge")

FULL_SYSTEM_PROMPT = SYSTEM_PROMPT

if _solutions_text:
    FULL_SYSTEM_PROMPT += "\n\n" + "=" * 60 + "\n"
    FULL_SYSTEM_PROMPT += "חלק ב: פתרונות רשמיים של מבחני מהט — למד מהם את שיטת הפתרון הנכונה!\n"
    FULL_SYSTEM_PROMPT += "השתמש בפתרונות האלה כדי:\n"
    FULL_SYSTEM_PROMPT += "1. ללמוד את צורת הפתרון המקובלת במבחני מהט\n"
    FULL_SYSTEM_PROMPT += "2. להבין אילו נוסחאות משתמשים לכל סוג שאלה\n"
    FULL_SYSTEM_PROMPT += "3. לתת תשובות מדויקות ומפורטות בסגנון הרשמי\n"
    FULL_SYSTEM_PROMPT += "4. כשסטודנט שואל שאלה — חפש דוגמה דומה בפתרונות ופתור בצורה דומה\n"
    FULL_SYSTEM_PROMPT += "=" * 60 + "\n\n"
    FULL_SYSTEM_PROMPT += _solutions_text

if _theory_text:
    FULL_SYSTEM_PROMPT += "\n\n" + _theory_text

_total_tokens = len(FULL_SYSTEM_PROMPT) // 4
print(f"[INIT] Total system prompt: {len(FULL_SYSTEM_PROMPT):,} chars (~{_total_tokens:,} tokens, {_total_tokens/10000:.1f}% of 1M context)")

_chat_gen_config = genai.GenerationConfig(
    temperature=0.3,
    max_output_tokens=8192,
)
_extract_gen_config = genai.GenerationConfig(
    temperature=0.1,
    max_output_tokens=4096,
)

model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    system_instruction=FULL_SYSTEM_PROMPT,
    generation_config=_chat_gen_config,
)
summary_model = genai.GenerativeModel(
    model_name=SUMMARY_MODEL_NAME,
    generation_config=_extract_gen_config,
)
# Dedicated model for batch-solving: uses Flash (fast + high rate limit) with full formula sheet
_batch_solve_config = genai.GenerationConfig(temperature=0.3, max_output_tokens=8192)
batch_solve_model = genai.GenerativeModel(
    model_name=SUMMARY_MODEL_NAME,
    system_instruction=FULL_SYSTEM_PROMPT,
    generation_config=_batch_solve_config,
)

CORRECTION_TRIGGER = "הנה הפתרון הנכון"

UPLOADS_DIR = os.path.join("static", "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


def _save_image_to_disk(image_b64: str, mime_type: str) -> str:
    """Save base64 image to static/uploads/ and return the URL path."""
    ext = "jpg"
    if "png" in mime_type:
        ext = "png"
    elif "webp" in mime_type:
        ext = "webp"
    filename = f"{_uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOADS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(base64.b64decode(image_b64))
    return f"/uploads/{filename}"


# ========== BACKGROUND LEARNING HELPERS ==========

def extract_and_save_learning(correction_text: str):
    """Summarize a correction and persist as a learning."""
    try:
        prompt = (
            "קרא את התיקון הבא שנתן הבוט לטעות שלו, "
            "וסכם במשפט אחד קצר בעברית: מה הייתה הטעות ומה הפתרון הנכון. "
            "כתוב רק את הסיכום, ללא כותרות.\n\n"
            f"{correction_text[:2000]}"
        )
        resp = summary_model.generate_content(prompt)
        summary = resp.text.strip()
        if summary:
            db.save_learning(summary)
    except Exception:
        pass


def _try_sync_solution_to_bank(user_text: str, bot_response: str):
    """If user's message matches a question in the bank, update its solution.
    Triggered when user sends a correction (הנה הפתרון הנכון) or solves via chat.
    """
    try:
        all_qs = db.get_questions()
        user_norm = _normalize_text(user_text)
        for q in all_qs:
            q_norm = _normalize_text(q["text"])
            # Match: user message contains most of the question text
            if len(q_norm) > 20 and len(user_norm) > 20:
                shorter, longer = (q_norm, user_norm) if len(q_norm) <= len(user_norm) else (user_norm, q_norm)
                if shorter in longer:
                    db.update_question(q["id"], solution=bot_response)
                    print(f"[SYNC] Updated solution for question #{q['id']}")
                    return
    except Exception as e:
        print(f"[SYNC] Error: {e}")


def extract_and_save_from_conversation(conv_text: str):
    """Extract key method from a deleted conversation and save as learning."""
    try:
        prompt = (
            "קרא את השיחה הבאה. אם יש בה פתרון לתרגיל מכונות חשמל, "
            "סכם בשורה אחת קצרה בעברית את הגישה והשיטה שהוצגה (לא את התוצאה). "
            "אם אין פתרון ממשי, השב 'אין'. כתוב רק את הסיכום.\n\n"
            f"{conv_text[:3000]}"
        )
        resp = summary_model.generate_content(prompt)
        summary = resp.text.strip()
        if summary and "אין" not in summary:
            db.save_learning(summary)
    except Exception:
        pass


def _call_extract_questions(prompt: str) -> list:
    resp = summary_model.generate_content(prompt)
    raw = resp.text.strip()
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        data = json.loads(match.group())
        return data.get("questions", [])
    return []


# ========== PDF → IMAGE EXTRACTION ==========

def _pdf_pages_to_images(pdf_path: str, dpi: int = 200) -> list:
    """Convert each PDF page to a PNG image.
    Returns list of (page_number, png_bytes).
    """
    pages = []
    doc = fitz.open(pdf_path)
    zoom = dpi / 72  # 72 is the default PDF DPI
    matrix = fitz.Matrix(zoom, zoom)
    for page_num in range(len(doc)):
        pix = doc[page_num].get_pixmap(matrix=matrix)
        png_bytes = pix.tobytes("png")
        pages.append((page_num + 1, png_bytes))
    doc.close()
    return pages


def _extract_questions_from_pdf_page(png_bytes: bytes, page_num: int) -> dict:
    """Send a PDF page image to Gemini Vision and extract questions.
    Returns {"questions": [...], "image_url": "/uploads/xxx.png"}.
    """
    # Save page image to disk
    b64 = base64.b64encode(png_bytes).decode()
    image_url = _save_image_to_disk(b64, "image/png")

    # Send to Gemini Vision
    parts = [
        {"mime_type": "image/png", "data": png_bytes},
        (
            'חלץ את כל שאלות/תרגילי מכונות חשמל מעמוד הבחינה הזה.\n'
            'לכל שאלה כתוב תיאור מלא וברור, כולל כל הנתונים המספריים.\n'
            'אם יש סרטוט מעגל — תאר אותו בקצרה (רכיבים, חיבורים, ערכים).\n'
            'אם העמוד לא מכיל שאלות (למשל עמוד כותרת או הוראות) — החזר רשימה ריקה.\n'
            'החזר JSON בפורמט הזה בלבד (ללא ```):\n'
            '{"questions": [{"text": "תיאור מלא של השאלה כולל נתונים", "topic": "נושא"}, ...]}\n'
            'אם אין שאלות: {"questions": []}'
        )
    ]
    try:
        resp = summary_model.generate_content(parts)
        raw = resp.text.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        questions = json.loads(match.group()).get("questions", []) if match else []
    except Exception:
        questions = []

    return {"questions": questions, "image_url": image_url, "page": page_num}


def _find_pdf_for_exam(exam_txt_filename: str) -> Optional[str]:
    """Check if a matching PDF exists in mahat_pdfs/ for a text exam file.
    exam_90619_2023_springA.txt → mahat_pdfs/exam_90619_2023_springA.pdf
    """
    pdf_name = exam_txt_filename.replace(".txt", ".pdf")
    pdf_path = os.path.join(_MAHAT_PDFS_DIR, pdf_name)
    if os.path.isfile(pdf_path):
        return pdf_path
    return None


# ========== AUTO-SOLVE & CLASSIFY ==========

_VALID_TOPICS = [
    "שנאים", "מנוע אסינכרוני", "גנרטור סינכרוני", "מנוע סינכרוני",
    "מנוע DC", "גנרטור DC", "הנעה חשמלית", "כללי",
]


def _classify_topic(text: str) -> str:
    """Classify a question into one of the valid topic categories using Gemini Flash."""
    topics_str = ", ".join(_VALID_TOPICS)
    prompt = (
        f"סווג את השאלה הבאה לאחד מהנושאים הבאים בלבד: {topics_str}\n"
        "החזר רק את שם הנושא, ללא הסבר.\n\n"
        f"שאלה: {text[:500]}"
    )
    try:
        resp = summary_model.generate_content(prompt)
        topic = resp.text.strip().strip('"').strip("'")
        # Validate — must be one of the known topics
        for valid in _VALID_TOPICS:
            if valid in topic:
                return valid
        return topic  # Return as-is, frontend will map via TOPIC_RULES
    except Exception:
        return "כללי"


def _classify_difficulty(text: str) -> int:
    """Rate question difficulty 1-3 using heuristics (no API call needed).
    1=easy, 2=medium, 3=hard. Based on text length, sub-questions, and keywords.
    """
    score = 0
    # Length indicator
    if len(text) > 400:
        score += 1
    if len(text) > 800:
        score += 1
    # Sub-questions count (א, ב, ג or a, b, c or 1., 2., 3.)
    import re as _re
    sub_qs = len(_re.findall(r'[אבגדהוזחטיכלמנ][.)\]:]', text))
    sub_qs += len(_re.findall(r'\b[abcdef][.)\]]', text, _re.IGNORECASE))
    sub_qs += len(_re.findall(r'\b\d+[.)\]]', text))
    if sub_qs >= 4:
        score += 2
    elif sub_qs >= 2:
        score += 1
    # Hard keywords
    hard_kw = ['מעגל תמורה', 'מקביליות', 'parallel', 'equivalent circuit',
               'phasor', 'פאזור', 'chopper', 'VFD', 'rectifier', 'מיישר',
               'transient', 'מעבר', 'harmonic', 'הרמוני']
    for kw in hard_kw:
        if kw.lower() in text.lower():
            score += 1
            break
    # Map score to 1-3
    if score <= 1:
        return 1  # easy
    elif score <= 3:
        return 2  # medium
    else:
        return 3  # hard


def _solve_question(text: str, image_url: str = "", use_batch_model: bool = False) -> str:
    """Solve a question using Gemini (with system prompt).
    use_batch_model=True uses Flash (faster, higher rate limit) for batch processing.
    Includes retry with backoff for rate-limit errors.
    Falls back to text-only if the image is rejected by the API.
    """
    solve_prompt = "פתור את התרגיל הבא שלב-אחר-שלב:\n\n" + text
    parts = []
    has_image = False

    # Attach image if available
    if image_url:
        try:
            img_path = os.path.join("static", image_url.lstrip("/"))
            if os.path.isfile(img_path):
                with open(img_path, "rb") as f:
                    img_bytes = f.read()
                ext = os.path.splitext(img_path)[1].lower()
                mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext.lstrip("."), "image/png")
                parts.append({"mime_type": mime, "data": img_bytes})
                has_image = True
        except Exception:
            pass

    parts.append(solve_prompt)
    target_model = batch_solve_model if use_batch_model else model

    # Retry with backoff for rate-limit errors
    for attempt in range(3):
        try:
            resp = target_model.generate_content(parts)
            return resp.text.strip()
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower():
                wait = 15 * (attempt + 1)
                print(f"[RATE-LIMIT] Waiting {wait}s before retry ({attempt+1}/3)...")
                time.sleep(wait)
            elif has_image and ("400" in err_str or "image" in err_str.lower() or "invalid" in err_str.lower()):
                # Image rejected by API — retry with text only
                print(f"[SOLVE] Image rejected, retrying text-only...")
                parts = [solve_prompt]
                has_image = False
                # Continue to next attempt (text-only)
            else:
                print(f"[WARN] Auto-solve failed: {e}")
                return ""
    print("[WARN] Auto-solve failed after 3 retries")
    return ""


# ---- RAG: find similar solved questions for context injection ----

_HEB_STOP = set("של על את זה זו הוא היא הם הן אם או גם כי לא עם כל מה אין יש".split())

def _tokenize_heb(text: str) -> set:
    """Tokenize Hebrew/English text into meaningful words (>2 chars, no stopwords)."""
    words = re.findall(r'[\u0590-\u05FFa-zA-Z]{2,}', text.lower())
    return {w for w in words if w not in _HEB_STOP and len(w) > 2}


def _find_similar_solved(user_text: str, limit: int = 3) -> list:
    """Find solved questions from the exercise bank most similar to user's message.
    Uses keyword overlap scoring with topic bonus.
    Returns list of dicts: [{text, topic, solution}, ...]
    """
    user_tokens = _tokenize_heb(user_text)
    if len(user_tokens) < 2:
        return []

    solved = db.get_solved_questions()
    if not solved:
        return []

    scored = []
    for q in solved:
        q_tokens = _tokenize_heb(q["text"])
        overlap = user_tokens & q_tokens
        if len(overlap) < 2:
            continue
        # Jaccard-like score (overlap / union), weighted by overlap size
        union_size = len(user_tokens | q_tokens)
        score = len(overlap) / union_size if union_size else 0
        # Bonus for more absolute matches
        score += len(overlap) * 0.05
        scored.append((score, q))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:limit]]


def _build_rag_context(user_text: str) -> str:
    """Build RAG context string from similar solved exercises."""
    similar = _find_similar_solved(user_text, limit=2)
    if not similar:
        return ""

    parts = ["[דוגמאות פתורות מבנק התרגילים — השתמש בסגנון פתרון דומה:]"]
    for i, q in enumerate(similar, 1):
        sol_preview = q["solution"][:800]  # cap solution length
        parts.append(
            f"\n--- דוגמה {i} ({q['topic']}) ---\n"
            f"שאלה: {q['text'][:400]}\n"
            f"פתרון: {sol_preview}"
        )
    return "\n".join(parts)


def _process_and_save_questions(questions: list, source: str, default_image_url: str = "") -> dict:
    """Process extracted questions: dedup → classify → solve → save.
    Returns {"saved": N, "duplicates": N, "solved": N, "results": [...]}.
    """
    saved = 0
    duplicates = 0
    solved = 0
    results = []

    for q in questions:
        text = q.get("text", "") if isinstance(q, dict) else str(q)
        if not text or len(text.strip()) < 10:
            continue

        # ── Dedup check ──
        if db.question_exists(text):
            duplicates += 1
            results.append({"text": text[:60], "status": "duplicate"})
            continue

        # ── Classify topic ──
        raw_topic = q.get("topic", "") if isinstance(q, dict) else ""
        topic = _classify_topic(text)

        # ── Get image URL ──
        image_url = (q.get("image_url", "") if isinstance(q, dict) else "") or default_image_url

        # ── Auto-solve (use Flash for batch) ──
        print(f"[SOLVE] Solving: {text[:60]}...")
        solution = _solve_question(text, image_url, use_batch_model=True)
        if solution:
            solved += 1

        # ── Classify difficulty ──
        difficulty = _classify_difficulty(text)

        # ── Save to DB ──
        qid = db.save_question(text, topic, source, solution, image_url)
        db.update_question(qid, difficulty=difficulty)
        saved += 1
        results.append({"id": qid, "text": text[:60], "status": "saved", "topic": topic, "has_solution": bool(solution)})

    return {"saved": saved, "duplicates": duplicates, "solved": solved, "results": results}


# ========== MODELS ==========

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    image_data: Optional[str] = None
    image_mime_type: Optional[str] = None


class QuestionBody(BaseModel):
    text: str
    topic: str = ""
    source: str = ""
    solution: str = ""
    image_url: str = ""


class ExtractExamsRequest(BaseModel):
    exam_file: Optional[str] = None  # specific exam filename to extract from


# ========== HELPERS ==========

def _build_gemini_history(history_rows):
    history = []
    for msg in history_rows:
        role = msg["role"] if msg["role"] == "user" else "model"
        history.append({"role": role, "parts": [msg["content"]]})
    return history


def _build_message_parts(request: ChatRequest):
    parts = []
    if request.image_data:
        img_bytes = base64.b64decode(request.image_data)
        parts.append({"mime_type": request.image_mime_type or "image/jpeg", "data": img_bytes})
    if request.message:
        parts.append(request.message)
    return parts if len(parts) > 1 else (parts[0] if parts else request.message)


def _user_text(request: ChatRequest) -> str:
    if request.image_data and not request.message:
        return "[תמונה]"
    elif request.image_data:
        return f"[תמונה] {request.message}"
    return request.message


# ========== CHAT ENDPOINTS ==========

@app.post("/api/chat")
async def chat(request: ChatRequest):
    conversation_id = request.conversation_id or db.create_conversation()
    history_rows = db.get_messages(conversation_id)

    gemini_history = _build_gemini_history(history_rows)

    # RAG: inject similar solved exercises as context
    rag_context = _build_rag_context(request.message or "")
    if rag_context:
        gemini_history = [
            {"role": "user", "parts": [rag_context]},
            {"role": "model", "parts": ["הבנתי, אשתמש בדוגמאות אלו כהשראה לסגנון ודרך הפתרון."]},
        ] + gemini_history

    chat_session = model.start_chat(history=gemini_history)
    user_text = _user_text(request)
    db.save_message(conversation_id, "user", user_text)

    try:
        response = chat_session.send_message(_build_message_parts(request))
        assistant_text = response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")

    db.save_message(conversation_id, "model", assistant_text)
    if not history_rows:
        db.update_conversation_title(conversation_id, user_text[:60] + ("..." if len(user_text) > 60 else ""))

    return {"response": assistant_text, "conversation_id": conversation_id}


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    conversation_id = request.conversation_id or db.create_conversation()
    history_rows = db.get_messages(conversation_id)

    gemini_history = _build_gemini_history(history_rows)

    # Inject past learnings into fresh conversations
    if not history_rows:
        learnings = db.get_learnings()
        if learnings:
            learnings_text = "לקחים מתיקונים קודמים שחשוב לזכור:\n" + "\n".join(f"• {l}" for l in learnings)
            gemini_history = [
                {"role": "user", "parts": [f"[זיכרון מערכת] {learnings_text}"]},
                {"role": "model", "parts": ["הבנתי, אקח לקחים אלו בחשבון בתשובות הבאות."]},
            ] + gemini_history

    # RAG: inject similar solved exercises as context
    rag_context = _build_rag_context(request.message or "")
    if rag_context:
        gemini_history = [
            {"role": "user", "parts": [rag_context]},
            {"role": "model", "parts": ["הבנתי, אשתמש בדוגמאות אלו כהשראה לסגנון ודרך הפתרון."]},
        ] + gemini_history

    chat_session = model.start_chat(history=gemini_history)
    message_to_send = _build_message_parts(request)
    user_text = _user_text(request)
    db.save_message(conversation_id, "user", user_text)
    is_new = not history_rows

    def generate():
        yield f"data: {json.dumps({'conversation_id': conversation_id})}\n\n"
        full_response = ""
        try:
            for chunk in chat_session.send_message(message_to_send, stream=True):
                try:
                    text = chunk.text
                    if text:
                        full_response += text
                        yield f"data: {json.dumps({'chunk': text})}\n\n"
                except (ValueError, AttributeError):
                    pass
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        db.save_message(conversation_id, "model", full_response)
        if is_new:
            db.update_conversation_title(conversation_id, user_text[:60] + ("..." if len(user_text) > 60 else ""))

        if CORRECTION_TRIGGER in user_text and full_response:
            threading.Thread(target=extract_and_save_learning, args=(full_response,), daemon=True).start()

        # Auto-sync: if user's question matches a bank exercise, update its solution
        if full_response and len(user_text) > 30:
            threading.Thread(target=_try_sync_solution_to_bank, args=(user_text, full_response), daemon=True).start()

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


# ========== CONVERSATION ENDPOINTS ==========

@app.get("/api/conversations")
async def get_conversations(search: str = ""):
    return db.get_conversations(search=search)


@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    return db.get_messages(conversation_id)


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    messages = db.get_messages(conversation_id)
    if messages:
        conv_text = "\n".join(
            f"{'משתמש' if m['role'] == 'user' else 'בוט'}: {m['content']}"
            for m in messages[-20:]
        )
        threading.Thread(target=extract_and_save_from_conversation, args=(conv_text,), daemon=True).start()
    db.delete_conversation(conversation_id)
    return {"status": "deleted"}


# ========== QUESTION BANK ENDPOINTS ==========

@app.get("/api/questions")
async def get_questions():
    return db.get_questions()


@app.post("/api/questions")
async def save_question(body: QuestionBody):
    # Prevent duplicates
    if db.question_exists(body.text):
        return {"id": -1, "status": "duplicate"}

    topic = body.topic
    solution = body.solution

    # Auto-classify if topic is empty or generic
    if not topic or topic in ("", "כללי", "לא ידוע"):
        topic = _classify_topic(body.text)

    # Auto-solve if no solution provided
    if not solution:
        solution = _solve_question(body.text, body.image_url)

    difficulty = _classify_difficulty(body.text)
    qid = db.save_question(body.text, topic, body.source, solution, body.image_url)
    db.update_question(qid, difficulty=difficulty)
    return {"id": qid, "status": "saved", "topic": topic, "has_solution": bool(solution)}


@app.put("/api/questions/{question_id}")
async def update_question_endpoint(question_id: int, body: dict):
    """Update a question's text, topic, solution, or source."""
    allowed = {"text", "topic", "solution", "source"}
    updates = {k: v for k, v in body.items() if k in allowed and v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    db.update_question(question_id, **updates)
    return {"status": "updated", "id": question_id, "fields": list(updates.keys())}


@app.post("/api/questions/save-from-chat")
async def save_question_from_chat(body: dict):
    """Save a chat response as a solved exercise in the bank.
    Expects: { text: user_question, solution: bot_response }
    Auto-classifies topic and checks for duplicates.
    """
    text = body.get("text", "").strip()
    solution = body.get("solution", "").strip()
    if not text or not solution:
        raise HTTPException(status_code=400, detail="text and solution are required")

    # Check for duplicates
    if db.question_exists(text):
        # Try to update the existing question's solution instead
        solved = db.get_solved_questions()
        all_qs = db.get_questions()
        for q in all_qs:
            if _normalize_text(q["text"]) == _normalize_text(text) or text[:50] in q["text"]:
                db.update_question(q["id"], solution=solution)
                return {"status": "updated", "id": q["id"], "message": "פתרון עודכן בשאלה קיימת"}
        return {"status": "duplicate", "message": "שאלה כבר קיימת"}

    topic = _classify_topic(text)
    qid = db.save_question(text, topic, "צ'אט", solution)
    return {"status": "saved", "id": qid, "topic": topic, "message": "נשמר לבנק התרגילים"}


@app.delete("/api/questions/{question_id}")
async def delete_question(question_id: int):
    db.delete_question(question_id)
    return {"status": "deleted"}


@app.post("/api/questions/deduplicate")
async def deduplicate_questions():
    """Remove duplicate questions from the database."""
    removed = db.deduplicate_questions()
    total = len(db.get_questions())
    return {"removed": removed, "remaining": total}


@app.post("/api/questions/batch-difficulty")
async def batch_classify_difficulty():
    """Classify difficulty for all questions that don't have one yet."""
    questions = db.get_questions()
    updated = 0
    for q in questions:
        if not q.get("difficulty"):
            d = _classify_difficulty(q["text"])
            db.update_question(q["id"], difficulty=d)
            updated += 1
    return {"updated": updated, "total": len(questions)}


@app.post("/api/questions/batch-solve")
async def batch_solve_questions():
    """Solve all unsolved questions — streams SSE progress events.
    Also re-classifies topics.
    """
    unsolved = db.get_unsolved_questions()

    def generate():
        total = len(unsolved)
        if total == 0:
            yield f"data: {json.dumps({'done': True, 'solved': 0, 'total': len(db.get_questions()), 'message': 'הכל כבר פתור!'})}\n\n"
            return

        yield f"data: {json.dumps({'status': 'start', 'total': total})}\n\n"

        solved_count = 0
        for i, q in enumerate(unsolved):
            qtext_short = q["text"][:50]
            print(f"[BATCH-SOLVE] ({i+1}/{total}) {qtext_short}...")
            yield f"data: {json.dumps({'status': 'solving', 'current': i+1, 'total': total, 'text': qtext_short})}\n\n"

            try:
                topic = _classify_topic(q["text"])
                solution = _solve_question(q["text"], q.get("image_url", ""), use_batch_model=True)

                updates = {}
                if solution:
                    updates["solution"] = solution
                    solved_count += 1
                if topic:
                    updates["topic"] = topic
                if updates:
                    db.update_question(q["id"], **updates)
            except Exception as e:
                print(f"[BATCH-SOLVE] Error on q#{q['id']}: {e}")

            yield f"data: {json.dumps({'status': 'progress', 'current': i+1, 'total': total, 'solved': solved_count})}\n\n"

        yield f"data: {json.dumps({'done': True, 'solved': solved_count, 'total': len(db.get_questions()), 'unsolved_attempted': total})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/questions/extract-image")
async def extract_questions_from_image(request: ChatRequest):
    """Extract questions from uploaded image → auto-classify → auto-solve → save to DB."""
    if not request.image_data:
        raise HTTPException(status_code=400, detail="Image required")
    mime = request.image_mime_type or "image/jpeg"
    img_bytes = base64.b64decode(request.image_data)

    # Save image to disk so it can be displayed alongside questions
    image_url = _save_image_to_disk(request.image_data, mime)

    parts = [
        {"mime_type": mime, "data": img_bytes},
        (
            'חלץ את כל שאלות/תרגילי מכונות חשמל מהתמונה.\n'
            'לכל שאלה כתוב תיאור מלא וברור, כולל כל הנתונים המספריים.\n'
            'אם יש סרטוט מעגל — תאר אותו בקצרה (רכיבים, חיבורים, ערכים).\n'
            'החזר JSON בפורמט הזה בלבד (ללא ```):\n'
            '{"questions": [{"text": "תיאור מלא של השאלה כולל נתונים", "topic": "נושא"}, ...]}\n'
            'אם אין שאלות: {"questions": []}'
        )
    ]
    try:
        resp = summary_model.generate_content(parts)
        raw = resp.text.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        questions = json.loads(match.group()).get("questions", []) if match else []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not questions:
        return {"saved": 0, "duplicates": 0, "solved": 0, "extracted": 0, "image_url": image_url}

    # ── Process: dedup → classify → solve → save ──
    # Attach image_url to all questions from this image
    for q in questions:
        if isinstance(q, dict):
            q["image_url"] = image_url

    source = request.message or "העלאת תמונה"
    print(f"[EXTRACT-IMG] {len(questions)} questions extracted, processing...")
    result = _process_and_save_questions(questions, source, default_image_url=image_url)

    return {**result, "extracted": len(questions), "image_url": image_url}


@app.get("/api/exams")
async def list_exams():
    """List available exam files from mahat_texts/ directory."""
    exams = []
    if not os.path.isdir(_MAHAT_TEXTS_DIR):
        return exams
    for fname in sorted(os.listdir(_MAHAT_TEXTS_DIR)):
        if not fname.startswith("exam_") or not fname.endswith(".txt"):
            continue
        # Parse: exam_{code}_{year}_{season}{moed}.txt
        parts = fname.replace(".txt", "").split("_")
        if len(parts) < 4:
            continue
        code = parts[1]
        year = parts[2]
        season_raw = parts[3]
        # Separate season from moed letter (e.g., "springA" → "spring", "A")
        moed = ""
        season_key = season_raw
        if season_raw and season_raw[-1] in "AB":
            moed = season_raw[-1]
            season_key = season_raw[:-1]
        season_heb = _SEASONS.get(season_key, season_key)
        code_name = _EXAM_CODES.get(code, code)
        moed_heb = {"A": "מועד א׳", "B": "מועד ב׳"}.get(moed, "")
        label = f"{code_name} — {year} {season_heb} {moed_heb}".strip()
        has_pdf = _find_pdf_for_exam(fname) is not None
        exams.append({"file": fname, "label": label, "code": code, "year": year, "has_pdf": has_pdf})
    return exams


@app.post("/api/questions/extract-exams")
async def extract_questions_from_exams(body: ExtractExamsRequest = ExtractExamsRequest()):
    """Extract questions from exam → auto-classify → auto-solve → save to DB.
    Everything happens server-side: dedup, topic classification, and solving.
    """
    source_label = "מבחנים"
    all_questions = []
    method = "text"

    if body.exam_file:
        safe_name = os.path.basename(body.exam_file)
        source_label = safe_name.replace(".txt", "").replace("exam_", "מבחן ")

        # ── Try PDF extraction first (preserves circuit diagrams) ──
        pdf_path = _find_pdf_for_exam(safe_name)
        if pdf_path:
            try:
                pages = _pdf_pages_to_images(pdf_path, dpi=200)
                for page_num, png_bytes in pages:
                    result = _extract_questions_from_pdf_page(png_bytes, page_num)
                    for q in result["questions"]:
                        q["image_url"] = result["image_url"]
                        q["page"] = result["page"]
                    all_questions.extend(result["questions"])
                method = "pdf_vision"
            except Exception as e:
                print(f"[WARN] PDF extraction failed for {safe_name}: {e}")
                all_questions = []  # Reset — will fallback to text

        # ── Fallback: text-based extraction ──
        if not all_questions:
            fpath = os.path.join(_MAHAT_TEXTS_DIR, safe_name)
            if not os.path.exists(fpath):
                raise HTTPException(status_code=404, detail=f"Exam file not found: {safe_name}")
            with open(fpath, "r", encoding="utf-8") as f:
                exam_text = f.read()
            text_to_process = exam_text[:15000]
            prompt = (
                'חלץ את כל שאלות/תרגילי הבחינה מהטקסט הבא.\n'
                'לכל שאלה כתוב תיאור קצר וברור, כולל כל הנתונים המספריים.\n'
                'החזר JSON בפורמט הזה בלבד (ללא ```):\n'
                '{"questions": [{"text": "תיאור מלא של השאלה כולל נתונים", "topic": "נושא"}, ...]}\n\n'
                + text_to_process
            )
            all_questions = _call_extract_questions(prompt)
            method = "text"
    else:
        exam_text = SYSTEM_PROMPT[-8000:]
        all_questions = _call_extract_questions(
            'חלץ את כל שאלות/תרגילי הבחינה מהטקסט הבא.\n'
            'לכל שאלה כתוב תיאור קצר וברור, כולל כל הנתונים המספריים.\n'
            'החזר JSON בפורמט הזה בלבד (ללא ```):\n'
            '{"questions": [{"text": "תיאור מלא של השאלה כולל נתונים", "topic": "נושא"}, ...]}\n\n'
            + exam_text[:15000]
        )

    if not all_questions:
        return {"saved": 0, "duplicates": 0, "solved": 0, "extracted": 0, "method": method, "source": source_label}

    # ── Process: dedup → classify → solve → save ──
    print(f"[EXTRACT] {len(all_questions)} questions extracted from {source_label}, processing...")
    result = _process_and_save_questions(all_questions, source_label)

    return {
        **result,
        "extracted": len(all_questions),
        "method": method,
        "source": source_label,
    }


# Serve static files (HTML frontend) - must be last
app.mount("/", StaticFiles(directory="static", html=True), name="static")

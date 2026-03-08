import base64
import os
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import Database
from prompts import SYSTEM_PROMPT

load_dotenv()

app = FastAPI(title="Electrical Machines Bot")
db = Database()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY not set. Create a .env file based on .env.example")

genai.configure(api_key=api_key)
model = genai.GenerativeModel(
    model_name="gemini-3-flash-preview",  # Gemini 3 Flash (March 2026)
    system_instruction=SYSTEM_PROMPT
)


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    image_data: Optional[str] = None       # base64-encoded image
    image_mime_type: Optional[str] = None  # e.g. "image/jpeg"


@app.post("/api/chat")
async def chat(request: ChatRequest):
    conversation_id = request.conversation_id

    # Create new conversation if none provided
    if not conversation_id:
        conversation_id = db.create_conversation()

    # Load existing history from DB
    history_rows = db.get_messages(conversation_id)

    # Build Gemini-compatible history (text only)
    gemini_history = []
    for msg in history_rows:
        role = msg["role"] if msg["role"] == "user" else "model"
        gemini_history.append({
            "role": role,
            "parts": [msg["content"]]
        })

    # Start chat session with history
    chat_session = model.start_chat(history=gemini_history)

    # Build message parts (text + optional image)
    parts = []
    if request.image_data:
        img_bytes = base64.b64decode(request.image_data)
        parts.append({"mime_type": request.image_mime_type or "image/jpeg", "data": img_bytes})
    if request.message:
        parts.append(request.message)
    message_to_send = parts if len(parts) > 1 else (parts[0] if parts else request.message)

    # Save user message to DB (text representation)
    user_text_for_db = request.message
    if request.image_data and not request.message:
        user_text_for_db = "[תמונה]"
    elif request.image_data:
        user_text_for_db = f"[תמונה] {request.message}"
    db.save_message(conversation_id, "user", user_text_for_db)

    # Send to Gemini
    try:
        response = chat_session.send_message(message_to_send)
        assistant_text = response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")

    # Save assistant response to DB
    db.save_message(conversation_id, "model", assistant_text)

    # Auto-title the conversation from the first user message
    if len(history_rows) == 0:
        title = user_text_for_db[:60] + ("..." if len(user_text_for_db) > 60 else "")
        db.update_conversation_title(conversation_id, title)

    return {
        "response": assistant_text,
        "conversation_id": conversation_id
    }


@app.get("/api/conversations")
async def get_conversations():
    return db.get_conversations()


@app.get("/api/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    return db.get_messages(conversation_id)


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    db.delete_conversation(conversation_id)
    return {"status": "deleted"}


# Serve static files (HTML frontend) - must be last
app.mount("/", StaticFiles(directory="static", html=True), name="static")

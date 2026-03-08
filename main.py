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


@app.post("/api/chat")
async def chat(request: ChatRequest):
    conversation_id = request.conversation_id

    # Create new conversation if none provided
    if not conversation_id:
        conversation_id = db.create_conversation()

    # Load existing history from DB
    history_rows = db.get_messages(conversation_id)

    # Build Gemini-compatible history (exclude the latest user message)
    gemini_history = []
    for msg in history_rows:
        # Gemini uses "model" for assistant role
        role = msg["role"] if msg["role"] == "user" else "model"
        gemini_history.append({
            "role": role,
            "parts": [msg["content"]]
        })

    # Start chat session with history
    chat_session = model.start_chat(history=gemini_history)

    # Save user message to DB
    db.save_message(conversation_id, "user", request.message)

    # Send to Gemini
    try:
        response = chat_session.send_message(request.message)
        assistant_text = response.text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")

    # Save assistant response to DB
    db.save_message(conversation_id, "model", assistant_text)

    # Auto-title the conversation from the first user message
    if len(history_rows) == 0:
        title = request.message[:60] + ("..." if len(request.message) > 60 else "")
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

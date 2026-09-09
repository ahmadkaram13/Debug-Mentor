import json
import time
import uuid
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()  # load .env so `uvicorn main:app --reload` works without manual export

from llm_client import get_completion, get_completion_stream, LLMError
from prompts import build_system_prompt, format_initial_submission

app = FastAPI(title="Code Debugging Mentor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-memory session store -------------------------------------------------
# session_id -> {
#   "messages": [...],
#   "hint_level": int,
#   "turns_since_progress": int,
#   "language": str | None,
#   "last_active": float,   # Unix timestamp — used for TTL pruning
# }
SESSIONS: Dict[str, dict] = {}

SESSION_TTL_SECONDS = 60 * 60 * 2  # 2 hours


def _prune_stale_sessions() -> None:
    """Remove sessions that haven't been active within SESSION_TTL_SECONDS."""
    cutoff = time.time() - SESSION_TTL_SECONDS
    stale = [sid for sid, s in SESSIONS.items() if s.get("last_active", 0) < cutoff]
    for sid in stale:
        SESSIONS.pop(sid, None)


def _get_or_create_session(session_id: Optional[str]) -> str:
    _prune_stale_sessions()
    if session_id and session_id in SESSIONS:
        SESSIONS[session_id]["last_active"] = time.time()
        return session_id
    new_id = session_id or str(uuid.uuid4())
    SESSIONS[new_id] = {
        "messages": [],
        "hint_level": 1,
        "turns_since_progress": 0,
        "language": None,
        "last_active": time.time(),
    }
    return new_id


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = ""
    code: Optional[str] = None       # only meaningfully used on the first turn
    error: Optional[str] = None      # only meaningfully used on the first turn
    language: Optional[str] = None   # e.g. "Python", "JavaScript" — used in system prompt
    im_stuck: bool = False           # student clicked "I'm still stuck" -> escalate hint level


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    hint_level: int


class ResetRequest(BaseModel):
    session_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


def _prepare_turn(request: ChatRequest):
    """Shared setup for both the blocking and streaming chat endpoints.
    Returns (session_id, session, llm_messages)."""
    session_id = _get_or_create_session(request.session_id)
    session = SESSIONS[session_id]

    is_first_turn = len(session["messages"]) == 0

    # Store language on first turn (or if caller provides it later).
    if request.language:
        session["language"] = request.language

    # Hint-level management:
    #   - im_stuck=True  → increment turns_since_progress, raise hint level (max 4)
    #   - im_stuck=False → decay turns_since_progress by 1 (not a hard reset to 0),
    #                       so the level drops gradually rather than snapping back to 1.
    if request.im_stuck:
        session["turns_since_progress"] += 1
        session["hint_level"] = min(4, 1 + session["turns_since_progress"])
    else:
        # Gradual decay: each non-stuck message brings the counter (and level) down by 1.
        session["turns_since_progress"] = max(0, session["turns_since_progress"] - 1)
        session["hint_level"] = max(1, 1 + session["turns_since_progress"])

    if is_first_turn:
        user_content = format_initial_submission(request.code, request.error, request.message)
    else:
        user_content = request.message.strip() or "(no additional message)"

    session["messages"].append({"role": "user", "content": user_content})

    system_prompt = build_system_prompt(
        hint_level=session["hint_level"],
        language=session.get("language"),
    )
    llm_messages = [{"role": "system", "content": system_prompt}] + session["messages"]
    return session_id, session, llm_messages


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    session_id, session, llm_messages = _prepare_turn(request)

    try:
        reply = get_completion(llm_messages)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))

    session["messages"].append({"role": "assistant", "content": reply})

    return ChatResponse(session_id=session_id, reply=reply, hint_level=session["hint_level"])


@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    """Server-Sent Events endpoint. Emits:
    - event: session  -> {session_id, hint_level}   (sent first)
    - event: delta     -> {delta: "..."}              (repeated, token/word chunks)
    - event: done       -> {full: "..."}               (once, full assembled reply)
    - event: error      -> {error: "..."}              (on failure, terminates stream)
    """
    session_id, session, llm_messages = _prepare_turn(request)

    def event_generator():
        yield (
            "event: session\n"
            f"data: {json.dumps({'session_id': session_id, 'hint_level': session['hint_level']})}\n\n"
        )
        full_reply = ""
        try:
            for chunk in get_completion_stream(llm_messages):
                full_reply += chunk
                yield f"event: delta\ndata: {json.dumps({'delta': chunk})}\n\n"
        except LLMError as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            return

        session["messages"].append({"role": "assistant", "content": full_reply})
        yield f"event: done\ndata: {json.dumps({'full': full_reply})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering if proxied
        },
    )


@app.post("/reset")
def reset(request: ResetRequest):
    SESSIONS.pop(request.session_id, None)
    return {"status": "reset"}


@app.get("/session/{session_id}/history")
def get_history(session_id: str) -> List[dict]:
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session["messages"]

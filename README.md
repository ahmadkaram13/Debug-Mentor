# Code Debugging Mentor 🧭

A Socratic debugging chatbot. Students paste their broken code and an error/traceback; the
mentor never hands back a fixed code block — instead it asks targeted questions, points at the
right area, and only gradually escalates hint specificity the longer the student stays stuck.

## How it works

- **Backend** (`backend/`, FastAPI): keeps per-session chat history in memory, tracks a
  `hint_level` (1–4) per session, injects that level into the system prompt each turn, and
  streams the LLM's reply back to the client token-by-token over Server-Sent Events.
- **`prompts.py`**: the actual Socratic behavior lives here — hard rules (never emit corrected
  code), guiding technique, and the 4-level hint escalation ladder.
- **`llm_client.py`**: swappable LLM backend — OpenAI (`gpt-4o`) or a local Ollama model
  (`llama3`), chosen with `LLM_PROVIDER`. Both a blocking call (`get_completion`) and a
  streaming generator (`get_completion_stream`) are provided.
- **Frontend — pick one:**
  - `frontend-react/` (recommended): a Vite + React chat UI that renders the reply live as it
    streams in, with a left-rail "hint ladder" showing the current escalation level (1–4,
    styled like debugger breakpoints), an "I'm still stuck 😩" button, and code-block-aware
    message rendering.
  - `frontend/`: the original Streamlit version (single blocking response per turn, no
    streaming). Kept as a lighter-weight alternative — same backend, same `/chat` endpoint.

## Setup

```bash
cd debug-mentor
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r backend/requirements.txt
cp .env.example .env
```

Edit `.env`:
- For **OpenAI**: set `LLM_PROVIDER=openai` and `OPENAI_API_KEY=sk-...`
- For **local Ollama**: set `LLM_PROVIDER=ollama`, run `ollama serve`, and
  `ollama pull llama3` first.

## Run — backend (required either way)

```bash
cd backend
export $(cat ../.env | xargs)   # or use python-dotenv / your shell's env loading
uvicorn main:app --reload --port 8000
```

## Run — React frontend (streaming, recommended)

```bash
cd frontend-react
cp .env.example .env            # VITE_BACKEND_URL=http://localhost:8000
npm install
npm run dev
```
Open http://localhost:5173. Replies stream in live; the left-rail ladder shows the current
hint level.

Production build: `npm run build` → static files in `frontend-react/dist/`, served by any
static host (or `npm run preview` to check it locally).

## Run — Streamlit frontend (non-streaming alternative)

```bash
cd frontend
pip install -r requirements.txt
export BACKEND_URL=http://localhost:8000
streamlit run app.py
```
Open the Streamlit URL it prints (usually http://localhost:8501).

## API reference

`POST /chat` — blocking, returns the full reply at once.
```json
{
  "session_id": "optional, omit on first message",
  "message": "free text from the student",
  "code": "optional, first turn only",
  "error": "optional, first turn only",
  "im_stuck": false
}
```
→ `{ "session_id": "...", "reply": "...", "hint_level": 1 }`

`POST /chat/stream` — same request body, Server-Sent Events response:
```
event: session
data: {"session_id": "...", "hint_level": 1}

event: delta
data: {"delta": "What do "}

event: delta
data: {"delta": "you expect..."}

event: done
data: {"full": "What do you expect..."}
```
On failure mid-stream: `event: error` with `data: {"error": "..."}` instead of `done`.

`POST /reset` → `{ "session_id": "..." }` clears a session.

`GET /session/{session_id}/history` → full message list for that session.

## Extending

- **Persistence**: swap the in-memory `SESSIONS` dict in `main.py` for Redis/Postgres if you
  need sessions to survive a restart or run across multiple backend instances.
- **Language-specific tuning**: pass a `language` field and tailor the system prompt (e.g.
  Python vs JavaScript idioms) in `prompts.py`.
- **Auth / rate limiting**: add before exposing this publicly — there's none built in.
- **Streaming everywhere**: the Streamlit frontend still uses the blocking `/chat` endpoint —
  swap it to `st.write_stream` against `/chat/stream` if you want streaming there too.

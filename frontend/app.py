import os

import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Code Debugging Mentor", page_icon="🧭", layout="centered")

st.title("🧭 Code Debugging Mentor")
st.caption(
    "A Socratic debugging buddy. Paste your code and error, and I'll ask questions "
    "to help you find the bug yourself — I won't just hand you the fix."
)

# --- Session state -------------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # list of (role, text) for display
if "submitted_initial" not in st.session_state:
    st.session_state.submitted_initial = False
if "hint_level" not in st.session_state:
    st.session_state.hint_level = 1


def reset_conversation():
    if st.session_state.session_id:
        try:
            requests.post(f"{BACKEND_URL}/reset", json={"session_id": st.session_state.session_id}, timeout=10)
        except requests.RequestException:
            pass
    st.session_state.session_id = None
    st.session_state.chat_history = []
    st.session_state.submitted_initial = False
    st.session_state.hint_level = 1


def call_backend(message: str, code: str = None, error: str = None, im_stuck: bool = False):
    payload = {
        "session_id": st.session_state.session_id,
        "message": message,
        "code": code,
        "error": error,
        "im_stuck": im_stuck,
    }
    resp = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    st.session_state.session_id = data["session_id"]
    st.session_state.hint_level = data["hint_level"]
    return data["reply"]


# --- Sidebar ---------------------------------------------------------------
with st.sidebar:
    st.subheader("Session")
    st.write(f"Hint level: **{st.session_state.hint_level}** / 4")
    st.progress(st.session_state.hint_level / 4)
    st.caption("Hint level rises the longer you're stuck, and resets when you make progress.")
    if st.button("🔄 Start a new problem", use_container_width=True):
        reset_conversation()
        st.rerun()

# --- Initial submission form -------------------------------------------
if not st.session_state.submitted_initial:
    with st.form("initial_form"):
        code = st.text_area("Paste the buggy code", height=220, placeholder="def add(a, b):\n    return a - b")
        error = st.text_area(
            "Error message / traceback / what's going wrong",
            height=120,
            placeholder="Expected 5 but got -1 when calling add(2, 3)",
        )
        message = st.text_input("Anything else you want to add? (optional)")
        submitted = st.form_submit_button("Get a hint")

    if submitted:
        if not code.strip() and not error.strip() and not message.strip():
            st.warning("Please paste some code or describe the issue first.")
        else:
            st.session_state.chat_history.append(("user", f"**Code:**\n```\n{code}\n```\n\n**Issue:** {error}\n\n{message}"))
            with st.spinner("Thinking of a good question..."):
                try:
                    reply = call_backend(message=message, code=code, error=error)
                except requests.RequestException as e:
                    reply = f"⚠️ Could not reach the backend: {e}"
            st.session_state.chat_history.append(("assistant", reply))
            st.session_state.submitted_initial = True
            st.rerun()

# --- Chat display + follow-up -------------------------------------------
else:
    for role, text in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(text)

    col1, col2 = st.columns([5, 1])
    with col2:
        stuck_clicked = st.button("I'm still stuck 😩", use_container_width=True)

    user_msg = st.chat_input("Respond with what you tried, what you found, or a follow-up question...")

    if stuck_clicked:
        st.session_state.chat_history.append(("user", "(I'm still stuck — can I get a stronger hint?)"))
        with st.spinner("Thinking..."):
            try:
                reply = call_backend(message="I'm still stuck, can you give me a stronger hint?", im_stuck=True)
            except requests.RequestException as e:
                reply = f"⚠️ Could not reach the backend: {e}"
        st.session_state.chat_history.append(("assistant", reply))
        st.rerun()

    if user_msg:
        st.session_state.chat_history.append(("user", user_msg))
        with st.spinner("Thinking..."):
            try:
                reply = call_backend(message=user_msg, im_stuck=False)
            except requests.RequestException as e:
                reply = f"⚠️ Could not reach the backend: {e}"
        st.session_state.chat_history.append(("assistant", reply))
        st.rerun()

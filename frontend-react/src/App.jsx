import { useEffect, useRef, useState } from 'react'
import HintLadder from './components/HintLadder.jsx'
import ChatMessage from './components/ChatMessage.jsx'
import IntakeForm from './components/IntakeForm.jsx'
import { streamChat, resetSession } from './api.js'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

export default function App() {
  const [sessionId, setSessionId] = useState(null)
  const [hintLevel, setHintLevel] = useState(1)
  const [messages, setMessages] = useState([]) // {role, content}
  const [phase, setPhase] = useState('intake') // 'intake' | 'chat'
  const [draft, setDraft] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [errorMsg, setErrorMsg] = useState(null)
  const [language, setLanguage] = useState('')

  const threadRef = useRef(null)
  const streamingIndexRef = useRef(null)
  const composerRef = useRef(null)

  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTop = threadRef.current.scrollHeight
    }
  }, [messages, isStreaming])

  function appendMessage(role, content) {
    setMessages((prev) => [...prev, { role, content }])
  }

  function runStream(payload) {
    setErrorMsg(null)
    setIsStreaming(true)

    // Reserve a placeholder assistant message to stream into.
    setMessages((prev) => {
      streamingIndexRef.current = prev.length
      return [...prev, { role: 'assistant', content: '' }]
    })

    streamChat(BACKEND_URL, payload, {
      onSession: ({ session_id, hint_level }) => {
        setSessionId(session_id)
        setHintLevel(hint_level)
      },
      onDelta: (delta) => {
        setMessages((prev) => {
          const next = [...prev]
          const idx = streamingIndexRef.current
          if (next[idx]) {
            next[idx] = { ...next[idx], content: next[idx].content + delta }
          }
          return next
        })
      },
      onDone: () => {
        setIsStreaming(false)
      },
      onError: (msg) => {
        setErrorMsg(msg)
        setIsStreaming(false)
      },
    }).catch((e) => {
      setErrorMsg(e.message || 'Something went wrong talking to the backend.')
      setIsStreaming(false)
    })
  }

  function handleIntakeSubmit({ code, error, message, language: lang }) {
    setLanguage(lang || '')
    const preview = [
      lang && `Language: ${lang}`,
      code.trim() && `Code:\n\`\`\`\n${code.trim()}\n\`\`\``,
      error.trim() && `Issue: ${error.trim()}`,
      message.trim(),
    ]
      .filter(Boolean)
      .join('\n\n')

    appendMessage('user', preview || '(shared code and error)')
    setPhase('chat')
    runStream({ session_id: sessionId, message, code, error, language: lang || undefined, im_stuck: false })
  }

  function handleSend() {
    const text = draft.trim()
    if (!text || isStreaming) return
    appendMessage('user', text)
    setDraft('')
    // Reset textarea height after clearing
    if (composerRef.current) {
      composerRef.current.style.height = 'auto'
    }
    runStream({ session_id: sessionId, message: text, language: language || undefined, im_stuck: false })
  }

  function handleStuck() {
    if (isStreaming) return
    appendMessage('user', "(I'm still stuck — can I get a stronger hint?)")
    runStream({
      session_id: sessionId,
      message: "I'm still stuck, can you give me a stronger hint?",
      language: language || undefined,
      im_stuck: true,
    })
  }

  async function handleReset() {
    await resetSession(BACKEND_URL, sessionId)
    setSessionId(null)
    setHintLevel(1)
    setMessages([])
    setPhase('intake')
    setDraft('')
    setLanguage('')
    setErrorMsg(null)
    setIsStreaming(false)
  }

  function handleComposerKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Auto-resize the composer textarea as the user types.
  function handleComposerInput(e) {
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }

  return (
    <div className="app-shell">
      <aside className="rail">
        <div className="brand">
          <span className="brand-mark">Debug Mentor</span>
          <span className="brand-sub">socratic // no spoilers</span>
        </div>
        <HintLadder hintLevel={hintLevel} />
        <div className="rail-footer">
          <button className="reset-btn" onClick={handleReset}>
            ↺ New problem
          </button>
        </div>
      </aside>

      <main className="main">
        {phase === 'intake' ? (
          <div style={{ overflowY: 'auto', flex: 1 }}>
            <IntakeForm onSubmit={handleIntakeSubmit} disabled={isStreaming} />
          </div>
        ) : (
          <>
            <div className="thread" ref={threadRef}>
              {messages.map((m, i) => (
                <ChatMessage
                  key={i}
                  role={m.role}
                  content={m.content}
                  streaming={isStreaming && i === streamingIndexRef.current}
                />
              ))}
            </div>

            {errorMsg && (
              <div className="error-banner">
                <div className="inner">{errorMsg}</div>
              </div>
            )}

            <div className="composer">
              <div className="composer-inner">
                <textarea
                  ref={composerRef}
                  rows={1}
                  placeholder="What did you try? What did you find?"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  onInput={handleComposerInput}
                  disabled={isStreaming}
                />
                <button className="stuck-btn" onClick={handleStuck} disabled={isStreaming}>
                  I'm stuck 😩
                </button>
                <div className="send-wrap">
                  <button className="send-btn" onClick={handleSend} disabled={isStreaming || !draft.trim()}>
                    Send
                  </button>
                  <span className="send-hint">↵ Enter</span>
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  )
}

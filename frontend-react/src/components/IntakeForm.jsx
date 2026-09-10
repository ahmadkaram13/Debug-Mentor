import { useState } from 'react'

const LANGUAGES = [
  'Python',
  'JavaScript',
  'TypeScript',
  'Java',
  'C',
  'C++',
  'C#',
  'Go',
  'Rust',
  'Ruby',
  'PHP',
  'Other',
]

export default function IntakeForm({ onSubmit, disabled }) {
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [language, setLanguage] = useState('')
  const [validationMsg, setValidationMsg] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!code.trim() && !error.trim() && !message.trim()) {
      setValidationMsg('Please paste some code or describe what\'s going wrong.')
      return
    }
    setValidationMsg('')
    onSubmit({ code, error, message, language })
  }

  return (
    <>
      <div className="intro">
        <h1>Debug Mentor</h1>
        <p>
          Paste the code that's misbehaving and what's going wrong. I won't fix it for you —
          I'll ask the questions that help you find it yourself.
        </p>
      </div>
      <form className="form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="language">Language</label>
          <select
            id="language"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="language-select"
          >
            <option value="">— select one —</option>
            {LANGUAGES.map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="code">Buggy code</label>
          <textarea
            id="code"
            rows={10}
            placeholder={'def add(a, b):\n    return a - b'}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="error">Error, traceback, or what you expected vs. what happened</label>
          <textarea
            id="error"
            rows={5}
            placeholder="Expected 5 but got -1 when calling add(2, 3)"
            value={error}
            onChange={(e) => setError(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="message">Anything else? (optional)</label>
          <input
            id="message"
            type="text"
            placeholder="I think it's something in the loop but I'm not sure"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
          />
        </div>
        {validationMsg && (
          <div className="intake-validation">{validationMsg}</div>
        )}
        <div className="submit-row">
          <button type="submit" className="primary-btn" disabled={disabled}>
            Get a hint
          </button>
        </div>
      </form>
    </>
  )
}

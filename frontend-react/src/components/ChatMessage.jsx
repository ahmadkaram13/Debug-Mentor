import { useState } from 'react'

// Copy text to clipboard and briefly show "Copied!" feedback.
function CopyButton({ text }) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <button className="copy-btn" onClick={handleCopy} title="Copy code">
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  )
}

/**
 * Markdown-lite renderer:
 *   1. Splits on ``` fenced blocks → <pre><code> with a Copy button.
 *   2. Within prose sections, splits on double-newlines → paragraph breaks.
 *   3. Within paragraphs, splits on `inline code` → <code>.
 */
function renderContent(text) {
  const blockParts = text.split(/```/g)
  return blockParts.map((part, i) => {
    if (i % 2 === 1) {
      // Inside a fenced block — strip an optional leading language tag line.
      const langMatch = part.match(/^([a-zA-Z0-9_+-]*)\n/)
      const cleaned = langMatch ? part.slice(langMatch[0].length) : part
      return (
        <div className="code-block-wrap" key={i}>
          <CopyButton text={cleaned} />
          <pre className="block">
            <code>{cleaned}</code>
          </pre>
        </div>
      )
    }

    // Prose: split on double-newlines to create paragraph breaks.
    const paragraphs = part.split(/\n\n+/)
    return (
      <span key={i}>
        {paragraphs.map((para, pi) => {
          // Within a paragraph, split on `inline code`.
          const inlineParts = para.split(/`([^`]+)`/g)
          const rendered = inlineParts.map((seg, j) =>
            j % 2 === 1 ? (
              <code className="inline" key={j}>{seg}</code>
            ) : (
              // Preserve single newlines as <br/>.
              seg.split('\n').map((line, li, arr) => (
                <span key={li}>
                  {line}
                  {li < arr.length - 1 && <br />}
                </span>
              ))
            )
          )
          return (
            <p className="msg-para" key={pi}>{rendered}</p>
          )
        })}
      </span>
    )
  })
}

export default function ChatMessage({ role, content, streaming }) {
  const isUser = role === 'user'
  return (
    <div className={`msg ${isUser ? 'user' : 'assistant'}`}>
      <div className={`avatar ${isUser ? 'user' : 'assistant'}`}>{isUser ? 'you' : '{ }'}</div>
      <div className="bubble">
        {renderContent(content)}
        {streaming && <span className="cursor-blink" />}
      </div>
    </div>
  )
}

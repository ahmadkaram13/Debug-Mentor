/**
 * Streams the backend's /chat/stream Server-Sent Events endpoint using fetch()
 * (EventSource doesn't support POST bodies, so we parse SSE frames manually).
 *
 * handlers: { onSession(({session_id, hint_level})), onDelta(text), onDone(fullText), onError(message) }
 */
export async function streamChat(backendUrl, payload, handlers) {
  const resp = await fetch(`${backendUrl}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!resp.ok || !resp.body) {
    let detail = `HTTP ${resp.status}`
    try {
      const j = await resp.json()
      detail = j.detail || detail
    } catch {
      /* ignore parse failure */
    }
    throw new Error(detail)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary
    while ((boundary = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      if (!rawEvent.trim()) continue

      let eventType = 'message'
      let dataStr = ''
      for (const line of rawEvent.split('\n')) {
        if (line.startsWith('event:')) eventType = line.slice(6).trim()
        else if (line.startsWith('data:')) dataStr += line.slice(5).trim()
      }
      if (!dataStr) continue

      let parsed
      try {
        parsed = JSON.parse(dataStr)
      } catch {
        continue
      }

      switch (eventType) {
        case 'session':
          handlers.onSession?.(parsed)
          break
        case 'delta':
          handlers.onDelta?.(parsed.delta)
          break
        case 'done':
          handlers.onDone?.(parsed.full)
          break
        case 'error':
          handlers.onError?.(parsed.error)
          break
        default:
          break
      }
    }
  }
}

export async function resetSession(backendUrl, sessionId) {
  if (!sessionId) return
  try {
    await fetch(`${backendUrl}/reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    })
  } catch {
    /* best-effort */
  }
}

const BASE = '/api'

export interface SseProgress {
  step: string
  finished: number
  total: number
  message: string
}

export interface SseCallbacks {
  onProgress?: (p: SseProgress) => void
  onResult?: (data: unknown) => void
  onError?: (message: string) => void
}

export async function streamSse(
  path: string,
  body: unknown,
  callbacks: SseCallbacks,
): Promise<void> {
  const response = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    callbacks.onError?.(`HTTP ${response.status}`)
    return
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let eventType = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        const jsonStr = line.slice(6)
        try {
          const data = JSON.parse(jsonStr)
          if (eventType === 'progress') callbacks.onProgress?.(data)
          else if (eventType === 'result') callbacks.onResult?.(data)
          else if (eventType === 'error') callbacks.onError?.(data.errors?.[0] ?? 'Unknown error')
        } catch {
          // skip malformed JSON
        }
      }
    }
  }
}

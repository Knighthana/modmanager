import { API_BASE } from './config'
import type { SseProgress, ProgressCallbacks } from './transport'

export type { SseProgress, ProgressCallbacks } from './transport'

const CONFIG_INDEX_KEY = 'modmanager:configIndex'
const CONFIG_INDEX_MISSING_MSG = '请先在设置页面连接配置文件'

function getConfigIndexJson(): string | null {
  let raw = sessionStorage.getItem(CONFIG_INDEX_KEY)
  if (!raw) {
    raw = localStorage.getItem(CONFIG_INDEX_KEY)
    if (raw) {
      // Write-through: keep request header source consistent.
      sessionStorage.setItem(CONFIG_INDEX_KEY, raw)
    }
  }
  if (!raw) return null
  try {
    JSON.parse(raw) // validate
    return raw
  } catch { return null }
}

async function resolveConfigIndexJson(): Promise<string | null> {
  const existing = getConfigIndexJson()
  if (existing) return existing

  try {
    const response = await fetch(`${API_BASE}/os/defaults`)
    if (!response.ok) return null
    const body = await response.json() as {
      data?: { userconfig_index?: { type?: string; string?: string } }
    }
    const idx = body.data?.userconfig_index
    if (!idx || typeof idx.type !== 'string' || typeof idx.string !== 'string' || !idx.string) {
      return null
    }

    const raw = JSON.stringify({ type: idx.type, string: idx.string })
    sessionStorage.setItem(CONFIG_INDEX_KEY, raw)
    localStorage.setItem(CONFIG_INDEX_KEY, raw)
    return raw
  } catch {
    return null
  }
}

export async function streamSse(
  path: string,
  body: unknown,
  callbacks: ProgressCallbacks,
): Promise<void> {
  const idx = await resolveConfigIndexJson()
  if (!idx) {
    callbacks.onError?.(CONFIG_INDEX_MISSING_MSG)
    return
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-UserConfig-Index': idx },
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
  callbacks.onComplete?.()
}

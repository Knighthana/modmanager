import { API_BASE } from './config'
import type { ApiResponse } from './transport'

export type { ApiResponse } from './transport'

const CONFIG_INDEX_KEY = 'modmanager:configIndex'

function getConfigIndex(): Record<string, string> | null {
  try {
    let raw = sessionStorage.getItem(CONFIG_INDEX_KEY)
    if (!raw) {
      raw = localStorage.getItem(CONFIG_INDEX_KEY)
    }
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed && parsed.string) return parsed
    return null
  } catch {
    return null
  }
}

export async function apiPost<T>(path: string, body: unknown): Promise<ApiResponse<T>> {
  const idx = getConfigIndex()
  if (!idx) {
    return { ok: false, data: null, errors: ['请先在设置页面连接配置文件'], warnings: [] }
  }
  let finalBody = body
  if (typeof body === 'object' && body !== null) {
    const b = body as Record<string, unknown>
    if (!('config_index' in b)) {
      finalBody = { ...b, config_index: idx }
    }
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(finalBody),
  })
  return res.json()
}

export async function apiGet<T>(path: string): Promise<ApiResponse<T>> {
  const idx = getConfigIndex()
  if (!idx) {
    return { ok: false, data: null, errors: ['请先在设置页面连接配置文件'], warnings: [] }
  }
  const query = `?config_index=${encodeURIComponent(idx.string)}`
  const res = await fetch(`${API_BASE}${path}${query}`)
  return res.json()
}

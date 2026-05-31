import { API_BASE } from './config'
import type { ApiResponse } from './transport'

export type { ApiResponse } from './transport'

const CONFIG_INDEX_KEY = 'modmanager:configIndex'
const CONFIG_INDEX_MISSING_MSG = '请先在设置页面连接配置文件'

function getConfigIndexJson(): string | null {
  let raw = sessionStorage.getItem(CONFIG_INDEX_KEY)
  if (!raw) {
    raw = localStorage.getItem(CONFIG_INDEX_KEY)
    if (raw) {
      // Write-through: once local fallback is used, session becomes source of truth.
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
    const res = await fetch(`${API_BASE}/os/defaults`)
    if (!res.ok) return null
    const body = await res.json() as ApiResponse<Record<string, unknown>>
    const data = body.data as Record<string, unknown> | null
    if (!data || typeof data !== 'object') return null

    const idx = data.userconfig_index
    if (!idx || typeof idx !== 'object') return null

    const type = (idx as Record<string, unknown>).type
    const stringPath = (idx as Record<string, unknown>).string
    if (typeof type !== 'string' || typeof stringPath !== 'string' || !stringPath) return null

    const raw = JSON.stringify({ type, string: stringPath })
    sessionStorage.setItem(CONFIG_INDEX_KEY, raw)
    localStorage.setItem(CONFIG_INDEX_KEY, raw)
    return raw
  } catch {
    return null
  }
}

export async function apiGetPublic<T>(path: string): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`)
  return res.json()
}

export async function apiPost<T>(path: string, body: unknown): Promise<ApiResponse<T>> {
  const idx = await resolveConfigIndexJson()
  if (!idx) return { ok: false, data: null, errors: [CONFIG_INDEX_MISSING_MSG], warnings: [] }

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-UserConfig-Index': idx },
    body: JSON.stringify(body),
  })
  return res.json()
}

export async function apiGet<T>(path: string): Promise<ApiResponse<T>> {
  const idx = await resolveConfigIndexJson()
  if (!idx) return { ok: false, data: null, errors: [CONFIG_INDEX_MISSING_MSG], warnings: [] }

  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'X-UserConfig-Index': idx },
  })
  return res.json()
}

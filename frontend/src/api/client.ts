import { API_BASE } from './config'
import type { ApiResponse } from './transport'

export type { ApiResponse } from './transport'

const CONFIG_INDEX_KEY = 'modmanager:configIndex'

function getConfigIndexJson(): string | null {
  let raw = sessionStorage.getItem(CONFIG_INDEX_KEY)
  if (!raw) raw = localStorage.getItem(CONFIG_INDEX_KEY)
  if (!raw) return null
  try {
    JSON.parse(raw) // validate
    return raw
  } catch { return null }
}

export async function apiPost<T>(path: string, body: unknown): Promise<ApiResponse<T>> {
  const idx = getConfigIndexJson()
  if (!idx) return { ok: false, data: null, errors: ['请先在设置页面连接配置文件'], warnings: [] }

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-UserConfig-Index': idx },
    body: JSON.stringify(body),
  })
  return res.json()
}

export async function apiGet<T>(path: string): Promise<ApiResponse<T>> {
  const idx = getConfigIndexJson()
  if (!idx) return { ok: false, data: null, errors: ['请先在设置页面连接配置文件'], warnings: [] }

  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'X-UserConfig-Index': idx },
  })
  return res.json()
}

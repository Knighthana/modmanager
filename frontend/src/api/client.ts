import { API_BASE } from './config'
import type { ApiResponse } from './transport'

export type { ApiResponse } from './transport'

export async function apiPost<T>(path: string, body: unknown): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.json()
}

export async function apiGet<T>(path: string): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`)
  return res.json()
}

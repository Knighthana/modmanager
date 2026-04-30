const BASE = '/api'

export interface ApiResponse<T = unknown> {
  ok: boolean
  data: T | null
  errors: string[]
  warnings: string[]
}

export async function apiPost<T>(path: string, body: unknown): Promise<ApiResponse<T>> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return res.json()
}

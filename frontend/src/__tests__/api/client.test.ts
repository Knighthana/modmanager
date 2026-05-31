import { beforeEach, describe, expect, it, vi } from 'vitest'

describe('client config_index bootstrap', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    sessionStorage.removeItem('modmanager:configIndex')
    localStorage.removeItem('modmanager:configIndex')
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  function createJsonResponse(payload: unknown, ok = true, status = 200): Response {
    return {
      ok,
      status,
      json: async () => payload,
    } as unknown as Response
  }

  it('writes through localStorage fallback into sessionStorage before request', async () => {
    localStorage.setItem('modmanager:configIndex', JSON.stringify({ type: 'path', string: '/from/local.json' }))

    fetchMock.mockResolvedValueOnce(createJsonResponse({ ok: true, data: { v: 1 }, errors: [], warnings: [] }))

    const { apiGet } = await import('../../api/client')
    const result = await apiGet<{ v: number }>('/test')

    expect(result.ok).toBe(true)
    expect(sessionStorage.getItem('modmanager:configIndex')).toBe(JSON.stringify({ type: 'path', string: '/from/local.json' }))
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/test'), expect.objectContaining({
      headers: expect.objectContaining({
        'X-UserConfig-Index': JSON.stringify({ type: 'path', string: '/from/local.json' }),
      }),
    }))
  })

  it('fetches /os/defaults when both storages are empty and then performs request', async () => {
    fetchMock
      .mockResolvedValueOnce(createJsonResponse({
        ok: true,
        data: { userconfig_index: { type: 'path', string: '/from/defaults.json' } },
        errors: [],
        warnings: [],
      }))
      .mockResolvedValueOnce(createJsonResponse({ ok: true, data: { done: true }, errors: [], warnings: [] }))

    const { apiPost } = await import('../../api/client')
    const result = await apiPost<{ done: boolean }>('/test', { x: 1 })

    expect(result.ok).toBe(true)
    expect(sessionStorage.getItem('modmanager:configIndex')).toBe(JSON.stringify({ type: 'path', string: '/from/defaults.json' }))
    expect(localStorage.getItem('modmanager:configIndex')).toBe(JSON.stringify({ type: 'path', string: '/from/defaults.json' }))
    expect(fetchMock).toHaveBeenNthCalledWith(1, expect.stringContaining('/os/defaults'))
    expect(fetchMock).toHaveBeenNthCalledWith(2, expect.stringContaining('/test'), expect.objectContaining({
      headers: expect.objectContaining({
        'X-UserConfig-Index': JSON.stringify({ type: 'path', string: '/from/defaults.json' }),
      }),
    }))
  })
})

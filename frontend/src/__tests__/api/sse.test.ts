import { describe, it, expect, vi, beforeEach } from 'vitest'

// We import the type only; the actual function is tested via mocks
import type { SseCallbacks } from '../../api/sse'

describe('SSE stream parsing logic', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  function createMockResponse(chunks: string[]): Response {
    const encoder = new TextEncoder()
    let index = 0

    return {
      ok: true,
      body: {
        getReader() {
          return {
            read() {
              if (index >= chunks.length) {
                return Promise.resolve({ done: true, value: undefined as unknown as Uint8Array })
              }
              const value = encoder.encode(chunks[index])
              index++
              return Promise.resolve({ done: false, value })
            },
          }
        },
      },
      status: 200,
    } as unknown as Response
  }

  it('parses progress events correctly', async () => {
    const chunks = [
      'event: progress\ndata: {"step":"aggregate","finished":1,"total":3,"message":"Aggregating rules"}\n\n',
      'event: result\ndata: {"ok":true,"data":null,"errors":[],"warnings":[]}\n\n',
    ]

    fetchMock.mockResolvedValue(createMockResponse(chunks))

    const callbacks: SseCallbacks = {
      onProgress: vi.fn(),
      onResult: vi.fn(),
      onError: vi.fn(),
    }

    // Dynamically import to use the live fetch mock
    const { streamSse } = await import('../../api/sse')
    await streamSse('/test', {}, callbacks)

    expect(callbacks.onProgress).toHaveBeenCalledWith({
      step: 'aggregate',
      finished: 1,
      total: 3,
      message: 'Aggregating rules',
    })
    expect(callbacks.onResult).toHaveBeenCalledWith({
      ok: true,
      data: null,
      errors: [],
      warnings: [],
    })
    expect(callbacks.onError).not.toHaveBeenCalled()
  })

  it('calls onError for HTTP error responses', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 500 })

    const callbacks: SseCallbacks = { onError: vi.fn() }
    const { streamSse } = await import('../../api/sse')
    await streamSse('/test', {}, callbacks)

    expect(callbacks.onError).toHaveBeenCalledWith('HTTP 500')
  })

  it('handles partial chunks (buffer boundary)', async () => {
    // Simulate a chunk that splits an SSE event across two reads
    const chunks = [
      'event: progress\nda',
      'ta: {"step":"test","finished":0,"total":1,"message":"Working"}\n\n',
      'event: result\ndata: {"ok":true}\n\n',
    ]

    fetchMock.mockResolvedValue(createMockResponse(chunks))

    const callbacks: SseCallbacks = {
      onProgress: vi.fn(),
      onResult: vi.fn(),
    }

    const { streamSse } = await import('../../api/sse')
    await streamSse('/test', {}, callbacks)

    expect(callbacks.onProgress).toHaveBeenCalledTimes(1)
    expect(callbacks.onResult).toHaveBeenCalledTimes(1)
  })

  it('skips malformed JSON without crashing', async () => {
    const chunks = [
      'event: progress\ndata: {invalid json}\n\n',
      'event: result\ndata: {"ok":true}\n\n',
    ]

    fetchMock.mockResolvedValue(createMockResponse(chunks))

    const callbacks: SseCallbacks = {
      onProgress: vi.fn(),
      onResult: vi.fn(),
      onError: vi.fn(),
    }

    const { streamSse } = await import('../../api/sse')
    await streamSse('/test', {}, callbacks)

    // Malformed progress should be silently skipped
    expect(callbacks.onProgress).not.toHaveBeenCalled()
    // Result should still be parsed
    expect(callbacks.onResult).toHaveBeenCalledWith({ ok: true })
    expect(callbacks.onError).not.toHaveBeenCalled()
  })

  it('handles error events', async () => {
    const chunks = [
      'event: error\ndata: {"ok":false,"data":null,"errors":["Something went wrong"],"warnings":[]}\n\n',
    ]

    fetchMock.mockResolvedValue(createMockResponse(chunks))

    const callbacks: SseCallbacks = { onError: vi.fn() }

    const { streamSse } = await import('../../api/sse')
    await streamSse('/test', {}, callbacks)

    expect(callbacks.onError).toHaveBeenCalledWith('Something went wrong')
  })
})

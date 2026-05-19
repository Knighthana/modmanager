import { http, HttpResponse } from 'msw'
import pipelineResult from '../data/pipeline-result.json'

/**
 * 构建 SSE 格式的 Response，供 streamSse 消费。
 */
function sseResponse(events: Array<{ event: string; data: unknown }>) {
  const body = events
    .map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}`)
    .join('\n\n') + '\n\n'
  return new HttpResponse(body, {
    headers: { 'Content-Type': 'text/event-stream' },
  })
}

export const pipelineHandlers = [
  // POST /api/pipeline/compute — 执行 pipeline（mock 阶段简化为 one-shot）
  http.post('/api/pipeline/compute', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: pipelineResult,
    })
  }),

  // GET /api/pipeline/status — 查询 pipeline 状态
  http.get('/api/pipeline/status', async () => {
    return HttpResponse.json({
      ok: true,
      data: {
        status: 'idle',
        lastRun: null,
        steps: [],
      },
    })
  }),

  // POST /api/pipeline/cancel — 取消正在运行的 pipeline
  http.post('/api/pipeline/cancel', async () => {
    return HttpResponse.json({
      ok: true,
      data: { cancelled: true },
    })
  }),

  // POST /api/pipeline/restore — 恢复备份
  http.post('/api/pipeline/restore', async () => {
    return sseResponse([
      { event: 'progress', data: { step: 'restore', finished: 0, total: 2, message: '开始恢复...' } },
      { event: 'progress', data: { step: 'restore', finished: 1, total: 2, message: '正在还原文件...' } },
      {
        event: 'result',
        data: {
          ok: true,
          data: { restored: ['file1.txt', 'file2.txt'], skipped: [], errors: [], orphans: [] },
        },
      },
    ])
  }),
]

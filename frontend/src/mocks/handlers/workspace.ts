import { http, HttpResponse } from 'msw'

// ── In-memory state for mock workspace ──────────────────────────────────
// This simulates what the backend would persist across requests.
let mockResultsTimestamp: string | null = null

export const workspaceHandlers = [
  // GET /api/workspace/status — 查询工作区状态
  http.get('/api/workspace/status', async () => {
    return HttpResponse.json({
      ok: true,
      data: {
        workspace: '/tmp/fixture/workspace',
        initialized: true,
        gameCount: 5,
        modCount: 10,
        lastModified: '2026-05-13T10:00:00Z',
        inputs: {
          aggregated_rule_path: '/tmp/fixture/aggregated_rule_set.json',
          rule_paths: [
            '/home/user/kmm_rules/my_mods.kmmrule.json',
            '/home/user/kmm_rules/extra.kmmrule.json',
          ],
        },
        results: {
          timestamp: mockResultsTimestamp,
          trees_count: null,
          mapping_count: null,
          warnings: [],
          errors: [],
          stats: null,
          inputs_hash: null,
        },
      },
    })
  }),

  // POST /api/workspace/save-config — 保存工作区配置
  http.post('/api/workspace/save-config', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: { saved: true, timestamp: new Date().toISOString() },
    })
  }),

  // POST /api/workspace/save-database — 保存工作区数据库
  http.post('/api/workspace/save-database', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: { saved: true, timestamp: new Date().toISOString() },
    })
  }),

  // POST /api/workspace/save-inputs — 保存工作区输入参数
  http.post('/api/workspace/save-inputs', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: { saved: true, timestamp: new Date().toISOString() },
      errors: [],
      warnings: [],
    })
  }),

  // POST /api/workspace/save-results — 保存计算结果摘要
  http.post('/api/workspace/save-results', async ({ request }) => {
    mockResultsTimestamp = new Date().toISOString()
    return HttpResponse.json({
      ok: true,
      data: { saved: true, timestamp: mockResultsTimestamp },
      errors: [],
      warnings: [],
    })
  }),
]

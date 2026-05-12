import { http, HttpResponse } from 'msw'
import configData from '../data/config.json'

export const configHandlers = [
  // POST /api/config/discover — 发现/加载用户配置
  http.post('/api/config/discover', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: configData,
    })
  }),

  // POST /api/config/save — 保存用户配置
  http.post('/api/config/save', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: { saved: true, timestamp: new Date().toISOString() },
    })
  }),

  // POST /api/config/validate — 验证配置
  http.post('/api/config/validate', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: { valid: true, errors: [], warnings: [] },
    })
  }),
]

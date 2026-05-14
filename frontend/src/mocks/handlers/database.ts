import { http, HttpResponse } from 'msw'
import dbData from '../data/database.json'

export const databaseHandlers = [
  // POST /api/database/read — 加载数据库
  http.post('/api/database/read', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: dbData,
    })
  }),

  // POST /api/database/generate — 生成数据库
  http.post('/api/database/generate', async () => {
    return HttpResponse.json({
      ok: true,
      data: dbData,
      warnings: [],
      errors: [],
    })
  }),

  // POST /api/database/save — 保存数据库
  http.post('/api/database/save', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: { saved: true, timestamp: new Date().toISOString() },
    })
  }),
]

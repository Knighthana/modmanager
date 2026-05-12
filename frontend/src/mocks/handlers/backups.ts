import { http, HttpResponse } from 'msw'
import backupsList from '../data/backups-list.json'

export const backupsHandlers = [
  // POST /api/backups/list — 列出备份
  http.post('/api/backups/list', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: backupsList,
    })
  }),

  // POST /api/backups/create — 创建备份
  http.post('/api/backups/create', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: { created: true, id: 'bak-' + Date.now(), timestamp: new Date().toISOString() },
    })
  }),

  // POST /api/backups/restore — 恢复备份
  http.post('/api/backups/restore', async ({ request }) => {
    return HttpResponse.json({
      ok: true,
      data: { restored: true, timestamp: new Date().toISOString() },
    })
  }),
]

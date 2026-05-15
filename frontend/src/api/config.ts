/**
 * API 配置 — 传输层配置点
 *
 * 支持三种部署方式：
 * 1. 开发中：127.0.0.1:8000（Vite proxy）
 * 2. 生产 Web：相对路径 /api（反向代理）
 * 3. Tauri：tauri:// 协议（未来）
 */

function getApiBase(): string {
  if (import.meta.env.MODE === 'development') {
    // 开发环境：Vite 会通过 vite.config.ts 的 proxy 转发
    return '/api'
  }

  // 生产环境：使用相对路径（依赖反向代理）
  return import.meta.env.VITE_API_BASE || '/api'
}

export const API_BASE = getApiBase()

export const API_ENDPOINTS = {
  CONFIG_DISCOVER: `${API_BASE}/config/discover`,
  CONFIG_SAVE: `${API_BASE}/config/save`,
  DATABASE_GENERATE: `${API_BASE}/database/generate`,
  DATABASE_READ: `${API_BASE}/database/read`,
  DATABASE_SAVE: `${API_BASE}/database/save`,
  PIPELINE_COMPUTE: `${API_BASE}/pipeline/compute`,
  PIPELINE_BACKUP: `${API_BASE}/pipeline/backup`,
  PIPELINE_APPLY: `${API_BASE}/pipeline/apply`,
  PIPELINE_RUN: `${API_BASE}/pipeline/run`,
  PIPELINE_RESTORE: `${API_BASE}/pipeline/restore`,
  PIPELINE_VISUALIZE: `${API_BASE}/pipeline/visualize`,
  RULES_SCAN: `${API_BASE}/rules/scan`,
  RULES_READ: `${API_BASE}/rules/read`,
  RULES_AGGREGATE: `${API_BASE}/rules/aggregate`,
  RULES_AFFECTED: `${API_BASE}/rules/affected-entries`,
  RULES_LOAD_AGGREGATED: `${API_BASE}/rules/load-aggregated`,
  BACKUPS_LIST: `${API_BASE}/backups/list`,
  BACKUPS_INSPECT: `${API_BASE}/backups/inspect`,
  // Workspace
  WORKSPACE_LIST: `${API_BASE}/workspace/list`,
  WORKSPACE_CREATE: `${API_BASE}/workspace/create`,
  WORKSPACE_SVG: (id: string) => `${API_BASE}/workspace/${id}/forest/svg`,
  WORKSPACE_MAPPING: (id: string) => `${API_BASE}/workspace/${id}/forest/mapping`,
} as const

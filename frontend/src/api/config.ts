/**
 * API 配置 — 传输层配置点
 *
 * 支持三种部署方式：
 * 1. 开发中：127.0.0.1:8000（Vite proxy）
 * 2. 生产 Web：相对路径 /api（反向代理）
 * 3. Tauri：tauri:// 协议（未来）
 *
 * 规则：
 * - ``API_BASE`` 仅由 ``apiPost`` / ``apiGet`` / ``streamSse`` 内部使用
 * - ``API_ENDPOINTS`` 中的值是**相对路径**，不含 ``API_BASE``
 * - 调用者传入相对路径，传输层负责拼接完整 URL
 */

function getApiBase(): string {
  if (import.meta.env.MODE === 'development') {
    return '/api'
  }
  return import.meta.env.VITE_API_BASE || '/api'
}

export const API_BASE = getApiBase()

export const API_ENDPOINTS = {
  CONFIG_DISCOVER: '/config/discover',
  CONFIG_SAVE: '/config/save',
  DATABASE_GENERATE: '/database/generate',
  DATABASE_READ: '/database/read',
  DATABASE_SAVE: '/database/save',
  PIPELINE_COMPUTE: '/pipeline/compute',
  PIPELINE_BACKUP: '/pipeline/backup',
  PIPELINE_APPLY: '/pipeline/apply',
  PIPELINE_RUN: '/pipeline/run',
  PIPELINE_RESTORE: '/pipeline/restore',
  PIPELINE_VISUALIZE: '/pipeline/visualize',
  RULES_SCAN: '/rules/scan',
  RULES_READ: '/rules/read',
  RULES_AGGREGATE: '/rules/aggregate',
  RULES_AFFECTED: '/rules/affected-entries',
  RULES_LOAD_AGGREGATED: '/rules/load-aggregated',
  BACKUPS_LIST: '/backups/list',
  BACKUPS_INSPECT: '/backups/inspect',
  // Workspace
  WORKSPACE_LIST: '/workspace/list',
  WORKSPACE_CREATE: '/workspace/create',
  WORKSPACE_SVG: (id: string) => `/workspace/${id}/forest/svg`,
  WORKSPACE_MAPPING: (id: string) => `/workspace/${id}/forest/mapping`,
} as const

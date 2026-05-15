/**
 * 传输层抽象接口
 *
 * 这是 HTTP 和 Tauri 实现的公共契约。
 * 任何传输方案（HTTP、WebSocket、Tauri invoke）
 * 都必须实现这两个接口。
 *
 * 见：DESIGN_FRONTEND_LAYER_INDEPENDENCE.md § 1 层传输适配层
 */

// ── Types ───────────────────────────────────────────────────────────────

/**
 * 通用 API 响应格式
 * 所有 POST 端点（非 SSE）都返回这个结构
 */
export interface ApiResponse<T = unknown> {
  ok: boolean
  data: T | null
  errors: string[]
  warnings: string[]
}

/**
 * SSE 进度报告格式
 */
export interface SseProgress {
  step: string
  finished: number
  total: number
  message: string
}

/**
 * SSE 回调接口
 */
export interface ProgressCallbacks {
  onProgress?: (p: SseProgress) => void
  onResult?: (data: unknown) => void
  onError?: (message: string) => void
  onComplete?: () => void
}

/**
 * POST 函数签名
 */
export type PostFn<T = unknown> = (
  path: string,
  body: unknown,
) => Promise<ApiResponse<T>>

/**
 * SSE 流式函数签名
 */
export type StreamSseFn = (
  path: string,
  body: unknown,
  callbacks: ProgressCallbacks,
) => Promise<void>

// ── Current implementation (HTTP) ───────────────────────────────────────
// Tauri 迁移时只需替换下面的两个 import 为目标实现

export { apiPost, apiPost as invoke } from './client'
export { streamSse } from './sse'

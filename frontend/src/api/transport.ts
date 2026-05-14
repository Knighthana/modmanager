/**
 * 传输层抽象接口
 *
 * 这是 HTTP 和 Tauri 实现的公共契约。
 * 任何传输方案（HTTP、WebSocket、Tauri invoke）
 * 都必须实现这两个接口。
 *
 * 见：DESIGN_FRONTEND_LAYER_INDEPENDENCE.md § 1 层传输适配层
 */

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
  step: string           // 当前步骤名称（如 "scanning", "computing"）
  finished: number       // 完成的项数
  total: number          // 总项数
  message: string        // 人类可读的消息
}

/**
 * SSE 回调接口
 * streamSse() 用这个回调通知上层进度
 */
export interface ProgressCallbacks {
  onProgress?: (p: SseProgress) => void
  onResult?: (data: unknown) => void
  onError?: (message: string) => void
  onComplete?: () => void
}

/**
 * POST 函数签名
 * 任何传输实现都需要符合这个签名
 */
export type PostFn<T = unknown> = (
  path: string,
  body: unknown,
) => Promise<ApiResponse<T>>

/**
 * SSE 流式函数签名
 * 任何传输实现都需要符合这个签名
 */
export type StreamSseFn = (
  path: string,
  body: unknown,
  callbacks: ProgressCallbacks,
) => Promise<void>

/**
 * Tauri 迁移时的实现示例（供参考，暂不启用）
 *
 * export async function apiPostTauri<T>(
 *   path: string,
 *   body: unknown,
 * ): Promise<ApiResponse<T>> {
 *   return invoke('api_invoke', { path, body })
 * }
 *
 * export async function streamSseTauri(
 *   path: string,
 *   body: unknown,
 *   callbacks: ProgressCallbacks,
 * ): Promise<void> {
 *   const unlisten = await listen(`progress_${path}`, (event) => {
 *     callbacks.onProgress?.(event.payload)
 *   })
 *   // ... 逻辑
 *   unlisten()
 * }
 */

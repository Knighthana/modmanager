import { ElMessage } from 'element-plus'

/**
 * 前端浏览器存储层 — sessionStorage 主读 + localStorage 留档。
 *
 * 设计：``DESIGN_WORKSPACE_MODEL.md`` §6
 *
 * 读写规则：
 * - sessionStorage 是主读源（Tab 隔离，刷新不丢）
 * - localStorage 是留档（仅新 Tab 初始化时回退一次）
 * - 改动时同时写两处
 *
 * 键规范：
 *   sessionStorage           localStorage
 *   ─────────────            ────────────
 *   sidebarCollapsed         sidebarCollapsed
 *   activeTab                （不存在）
 *   currentWorkspaceId       （不存在）
 *   uiState:datasource       uiState:datasource
 *   uiState:{workspace_id}   uiState:{workspace_id}
 */

const PREFIX = 'modmanager:'

// ── Internal helpers ──────────────────────────────────────────────────────

function _sessionKey(key: string): string {
  return PREFIX + key
}

function _localKey(key: string): string {
  return PREFIX + key
}

function _tryParse(raw: string | null): unknown | null {
  if (raw === null) return null
  try { return JSON.parse(raw) } catch { return null }
}

// ── Public API ────────────────────────────────────────────────────────────

/** Read a value: sessionStorage first, fallback to localStorage (then promote). */
export function loadPersistent<T>(key: string): T | null {
  // 1. sessionStorage (main source)
  const sessRaw = sessionStorage.getItem(_sessionKey(key))
  if (sessRaw !== null) return _tryParse(sessRaw) as T | null

  // 2. localStorage (fallback for new tabs)
  const localRaw = localStorage.getItem(_localKey(key))
  if (localRaw !== null) {
    const val = _tryParse(localRaw) as T | null
    if (val !== null) {
      // Promote to sessionStorage so subsequent reads skip localStorage
      sessionStorage.setItem(_sessionKey(key), JSON.stringify(val))
    }
    return val
  }
  return null
}

/** Write a value to both sessionStorage and localStorage (write-through). */
export function savePersistent(key: string, value: unknown): void {
  try {
    const payload = JSON.stringify(value)
    sessionStorage.setItem(_sessionKey(key), payload)
    localStorage.setItem(_localKey(key), payload)
  } catch {
    ElMessage.warning('偏好保存失败')
  }
}

/** Remove a value from both storages. */
export function clearPersistent(key: string): void {
  try {
    sessionStorage.removeItem(_sessionKey(key))
    localStorage.removeItem(_localKey(key))
  } catch {
    // ignore
  }
}

// ── Convenience typed helpers ────────────────────────────────────────────

export function loadSidebarCollapsed(): boolean {
  return loadPersistent<boolean>('sidebarCollapsed') ?? false
}

export function saveSidebarCollapsed(collapsed: boolean): void {
  savePersistent('sidebarCollapsed', collapsed)
}

export function loadActiveTab(): string {
  return loadPersistent<string>('activeTab') ?? ''
}

export function saveActiveTab(tab: string): void {
  sessionStorage.setItem(PREFIX + 'activeTab', tab)
  // NOT written to localStorage — activeTab is ephemeral
}

export function loadCurrentWorkspaceId(): string | null {
  return loadPersistent<string>('currentWorkspaceId')
}

export function saveCurrentWorkspaceId(id: string): void {
  sessionStorage.setItem(PREFIX + 'currentWorkspaceId', id)
  // NOT written to localStorage — workspace_id is tab-scoped
}

export function loadUiState<T>(scope: string): T | null {
  return loadPersistent<T>(`uiState:${scope}`)
}

export function saveUiState(scope: string, state: unknown): void {
  savePersistent(`uiState:${scope}`, state)
}

export function clearUiState(scope: string): void {
  clearPersistent(`uiState:${scope}`)
}

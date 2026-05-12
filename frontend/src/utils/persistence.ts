import { ElMessage } from 'element-plus'

/**
 * 纯 UI 状态持久化层。
 *
 * 职责：仅持久化无后端参与的 UI 状态（tab 位置、sidebar 折叠、可见性 toggle、表单输入）。
 * 业务数据（扫描结果、pipeline 结果、branch 决策）由后端 workspace 管理，不经过此层。
 *
 * Current implementation uses ``localStorage`` with a ``modmanager:`` prefix.
 * A ``TauriStoreAdapter`` is reserved for future Tauri integration.
 */

interface PersistenceAdapter {
  save(key: string, value: unknown): void
  load<T>(key: string): T | null
  clear(key: string): void
}

class LocalStorageAdapter implements PersistenceAdapter {
  save(key: string, value: unknown): void {
    try {
      localStorage.setItem(`modmanager:${key}`, JSON.stringify(value))
    } catch {
      ElMessage.warning('偏好保存失败，下次启动可能丢失设置')
    }
  }

  load<T>(key: string): T | null {
    try {
      const raw = localStorage.getItem(`modmanager:${key}`)
      if (raw === null) return null
      return JSON.parse(raw) as T
    } catch {
      ElMessage.warning('偏好读取失败，部分设置将被重置')
      return null
    }
  }

  clear(key: string): void {
    try {
      localStorage.removeItem(`modmanager:${key}`)
    } catch {
      ElMessage.warning('偏好清理失败')
    }
  }
}

// Reserved for future Tauri integration
// class TauriStoreAdapter implements PersistenceAdapter { ... }

export function createPersistence(): PersistenceAdapter {
  return new LocalStorageAdapter()
}

export type { PersistenceAdapter }

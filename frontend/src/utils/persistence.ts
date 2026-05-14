import { ElMessage } from 'element-plus'

/**
 * 纯 UI 状态持久化层 + workspace 数据聚合。
 *
 * 职责边界：
 * - UI 状态：tab 位置、sidebar 折叠、可见性 toggle、表单输入（无后端参与）
 * - workspace 数据：单一 ``modmanager:workspace`` key 下聚合
 *   - ``workspace.lastDatabase``：用户最近选择的 database name
 *   - ``workspace.perDatabase[name].decisions``：managedEntries + branchDecisions
 *   - ``workspace.perDatabase[name].lastComputeSummary``：trees_count、mapping_count 等摘要
 *   - ``workspace.aggregatedRuleSet``：聚合后的规则集 dict
 *   - ``workspace.aggregatedRuleHash``：规则集的哈希值
 * - 不存 database 扫描结果（由后端按 name 管理）
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

// ── Workspace helpers ────────────────────────────────────────────────────
// These replace the previous scattered key pattern (lastDatabase, decisions:*,
// results:*, aggregatedRuleSet) with a single ``modmanager:workspace`` key.

import type { WorkspaceData } from '../types'

function defaultWorkspace(): WorkspaceData {
  return {
    lastDatabase: '',
    perDatabase: {},
    aggregatedRuleSet: null,
    aggregatedRuleHash: '',
    aggregatedRuleMeta: null,
  }
}

/** Load the full workspace object from localStorage. */
export function loadWorkspace(): WorkspaceData {
  const pers = createPersistence()
  return pers.load<WorkspaceData>('workspace') ?? defaultWorkspace()
}

/** Save the full workspace object to localStorage. */
export function saveWorkspace(ws: WorkspaceData): void {
  const pers = createPersistence()
  pers.save('workspace', ws)
}

/** Compute a simple hash from an arbitrary value (for aggregatedRuleHash). */
export function simpleHash(obj: unknown): string {
  const str = JSON.stringify(obj)
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash |= 0
  }
  return (hash >>> 0).toString(36)
}

/** Abstract persistence layer for cross-tab / cross-session state.
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
    localStorage.setItem(`modmanager:${key}`, JSON.stringify(value))
  }

  load<T>(key: string): T | null {
    const raw = localStorage.getItem(`modmanager:${key}`)
    if (raw === null) return null
    try {
      return JSON.parse(raw) as T
    } catch {
      return null
    }
  }

  clear(key: string): void {
    localStorage.removeItem(`modmanager:${key}`)
  }
}

// Reserved for future Tauri integration
// class TauriStoreAdapter implements PersistenceAdapter { ... }

export function createPersistence(): PersistenceAdapter {
  return new LocalStorageAdapter()
}

export type { PersistenceAdapter }

import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ComputeSummary {
  treesCount: number
  mappingCount: number
  warnings: string[]
  errors: string[]
  inputsHash: string
  timestamp: string
}

export interface DatabaseState {
  selectedRulePaths: string[]
  managedEntries: {
    game: Record<string, string[]>
    mod: Record<string, string[]>
  }
  branchDecisions: Record<string, string>
  lastComputeSummary: ComputeSummary | null
}

export interface UiState {
  sidebarCollapsed: boolean
  activeTab: string
  libraryVisibility: Record<number, boolean>
  gameVisibility: Record<number, boolean>
}

export interface WorkspaceData {
  lastDatabase: string
  perDatabase: Record<string, DatabaseState>
  uiState: UiState
}

const STORAGE_KEY = 'modmanager:workspace'

/**
 * 前端工作区状态管理
 *
 * 单一真相源：localStorage 的唯一写者。
 * 所有其他模块通过本 store 访问和修改工作区数据，
 * 本 store 负责 flush 回 localStorage。
 *
 * 不包含内容：
 * - aggregatedRuleSet（在 useComputeStore 的内存中，不持久化）
 * - database 完整数据（后端文件权威，按需加载）
 * - 扫描结果（在 useDataSourceStore 的内存中，不持久化）
 */
export const useWorkspaceStore = defineStore('workspace', () => {
  // ── state ──
  const lastDatabase = ref<string>('')
  const perDatabase = ref<Record<string, DatabaseState>>({})
  const uiState = ref<UiState>({
    sidebarCollapsed: false,
    activeTab: '',
    libraryVisibility: {},
    gameVisibility: {},
  })

  // ── persistence helpers ──
  /**
   * 从 localStorage 加载工作区
   * 若不存在则初始化为空
   */
  function loadWorkspace() {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      try {
        const data = JSON.parse(stored) as WorkspaceData
        lastDatabase.value = data.lastDatabase || ''
        perDatabase.value = data.perDatabase || {}
        uiState.value = data.uiState || {
          sidebarCollapsed: false,
          activeTab: '',
          libraryVisibility: {},
          gameVisibility: {},
        }
      } catch {
        console.warn('Failed to parse workspace data, reinitializing')
        reset()
      }
    }
  }

  /**
   * 保存工作区到 localStorage
   * 每次修改状态后应立即调用以确保数据持久化
   */
  function saveWorkspace() {
    const data: WorkspaceData = {
      lastDatabase: lastDatabase.value,
      perDatabase: perDatabase.value,
      uiState: uiState.value,
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  }

  /**
   * 重置工作区为初始状态
   */
  function reset() {
    lastDatabase.value = ''
    perDatabase.value = {}
    uiState.value = {
      sidebarCollapsed: false,
      activeTab: '',
      libraryVisibility: {},
      gameVisibility: {},
    }
    localStorage.removeItem(STORAGE_KEY)
  }

  // ── actions for database state ──
  /**
   * 切换当前数据库并确保其状态已初始化
   */
  function switchDatabase(databaseName: string) {
    lastDatabase.value = databaseName
    if (!perDatabase.value[databaseName]) {
      perDatabase.value[databaseName] = {
        selectedRulePaths: [],
        managedEntries: { game: {}, mod: {} },
        branchDecisions: {},
        lastComputeSummary: null,
      }
    }
    saveWorkspace()
  }

  /**
   * 更新指定数据库的规则路径选择
   */
  function setSelectedRulePaths(databaseName: string, paths: string[]) {
    if (!perDatabase.value[databaseName]) {
      perDatabase.value[databaseName] = {
        selectedRulePaths: [],
        managedEntries: { game: {}, mod: {} },
        branchDecisions: {},
        lastComputeSummary: null,
      }
    }
    perDatabase.value[databaseName]!.selectedRulePaths = paths
    saveWorkspace()
  }

  /**
   * 更新指定数据库的托管条目筛选
   */
  function setManagedEntries(
    databaseName: string,
    entries: { game: Record<string, string[]>; mod: Record<string, string[]> },
  ) {
    if (!perDatabase.value[databaseName]) {
      perDatabase.value[databaseName] = {
        selectedRulePaths: [],
        managedEntries: { game: {}, mod: {} },
        branchDecisions: {},
        lastComputeSummary: null,
      }
    }
    perDatabase.value[databaseName]!.managedEntries = entries
    saveWorkspace()
  }

  /**
   * 更新指定数据库的分枝裁决
   */
  function setBranchDecision(databaseName: string, rootPath: string, chosenSource: string) {
    if (!perDatabase.value[databaseName]) {
      perDatabase.value[databaseName] = {
        selectedRulePaths: [],
        managedEntries: { game: {}, mod: {} },
        branchDecisions: {},
        lastComputeSummary: null,
      }
    }
    perDatabase.value[databaseName]!.branchDecisions[rootPath] = chosenSource
    saveWorkspace()
  }

  /**
   * 清除指定数据库的所有分枝裁决
   */
  function clearBranchDecisions(databaseName: string) {
    if (perDatabase.value[databaseName]) {
      perDatabase.value[databaseName]!.branchDecisions = {}
      saveWorkspace()
    }
  }

  /**
   * 更新指定数据库的计算摘要
   */
  function setLastComputeSummary(databaseName: string, summary: ComputeSummary) {
    if (!perDatabase.value[databaseName]) {
      perDatabase.value[databaseName] = {
        selectedRulePaths: [],
        managedEntries: { game: {}, mod: {} },
        branchDecisions: {},
        lastComputeSummary: null,
      }
    }
    perDatabase.value[databaseName]!.lastComputeSummary = summary
    saveWorkspace()
  }

  // ── actions for ui state ──
  /**
   * 更新库可见性状态
   */
  function setLibraryVisibility(visibility: Record<number, boolean>) {
    uiState.value.libraryVisibility = visibility
    saveWorkspace()
  }

  /**
   * 更新游戏可见性状态
   */
  function setGameVisibility(visibility: Record<number, boolean>) {
    uiState.value.gameVisibility = visibility
    saveWorkspace()
  }

  /**
   * 更新侧栏折叠状态
   */
  function setSidebarCollapsed(collapsed: boolean) {
    uiState.value.sidebarCollapsed = collapsed
    saveWorkspace()
  }

  /**
   * 更新当前活跃标签
   */
  function setActiveTab(tab: string) {
    uiState.value.activeTab = tab
    saveWorkspace()
  }

  return {
    // state
    lastDatabase,
    perDatabase,
    uiState,
    // persistence
    loadWorkspace,
    saveWorkspace,
    reset,
    // database actions
    switchDatabase,
    setSelectedRulePaths,
    setManagedEntries,
    setBranchDecision,
    clearBranchDecisions,
    setLastComputeSummary,
    // ui actions
    setLibraryVisibility,
    setGameVisibility,
    setSidebarCollapsed,
    setActiveTab,
  }
})

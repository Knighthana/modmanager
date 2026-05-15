/**
 * useAppStore — 组件读写浏览器存储的唯一入口（Pinia store）。
 *
 * 封装 persistence.ts 的所有导出函数为 reactive action。
 * 组件不允许直接 import persistence.ts。
 *
 * 设计：``DESIGN_FRONTEND_LAYER_INDEPENDENCE.md`` §2.1
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  loadPersistent,
  savePersistent,
  clearPersistent,
  loadUiState,
  saveUiState,
  clearUiState,
  loadCurrentWorkspaceId,
  saveCurrentWorkspaceId,
  loadSidebarCollapsed,
  saveSidebarCollapsed,
  loadActiveTab,
  saveActiveTab,
  migrateOldWorkspace,
} from '../utils/persistence'

export const useAppStore = defineStore('app', () => {
  // ── Reactive state (initialised from persistence) ──────────────────

  const sidebarCollapsed = ref(loadSidebarCollapsed())
  const activeTab = ref(loadActiveTab())
  const currentWorkspaceId = ref(loadCurrentWorkspaceId())

  // ── Actions ───────────────────────────────────────────────────────

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
    saveSidebarCollapsed(sidebarCollapsed.value)
  }

  function setSidebarCollapsed(collapsed: boolean) {
    sidebarCollapsed.value = collapsed
    saveSidebarCollapsed(collapsed)
  }

  function setActiveTab(tab: string) {
    activeTab.value = tab
    saveActiveTab(tab)
  }

  function setCurrentWorkspaceId(id: string | null) {
    currentWorkspaceId.value = id
    if (id) saveCurrentWorkspaceId(id)
  }

  // ── UI state (per-scope keyed) ────────────────────────────────────

  function loadUiStateFor<T>(scope: string): T | null {
    return loadUiState<T>(scope)
  }

  function saveUiStateFor(scope: string, state: unknown) {
    saveUiState(scope, state)
  }

  function clearUiStateFor(scope: string) {
    clearUiState(scope)
  }

  // ── Generic persistent read/write (for one-off keys) ──────────────

  function load<T>(key: string): T | null {
    return loadPersistent<T>(key)
  }

  function save(key: string, value: unknown) {
    savePersistent(key, value)
  }

  function clear(key: string) {
    clearPersistent(key)
  }

  // ── Lifecycle ─────────────────────────────────────────────────────

  function init() {
    migrateOldWorkspace()
    sidebarCollapsed.value = loadSidebarCollapsed()
    activeTab.value = loadActiveTab()
    currentWorkspaceId.value = loadCurrentWorkspaceId()
  }

  return {
    // state
    sidebarCollapsed,
    activeTab,
    currentWorkspaceId,
    // actions
    toggleSidebar,
    setSidebarCollapsed,
    setActiveTab,
    setCurrentWorkspaceId,
    loadUiStateFor,
    saveUiStateFor,
    clearUiStateFor,
    load,
    save,
    clear,
    init,
  }
})

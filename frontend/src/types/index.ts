/** @deprecated 使用 TreeNode */
export interface ForestNode {
  path: string
  destin_mixed_id: string
  changerequest: Changerequest[]
  warning?: string
  candidates?: string[]
}

export interface TreeNode {
  root_path: string           // 树的根路径（旧: ForestNode.path）
  destin_mixed_id: string
  changerequest: Changerequest[]
  refs: string[]              // 引用的其他树根路径
  resolved_state: 'pending' | 'kept' | 'deleted' | 'failed' | 'skipped'
  warning?: string
  candidates?: string[]
}

export interface Changerequest {
  path: string
  action: string
  action_order: number
  provenance_ref: string
  sidecar_ref: string
  mixed_id: string
  hashtype: string
  hashvalue: string
}

export interface MappingEntry {
  path: string
  request: Changerequest
}

export interface ConflictItem {
  root_path: string           // 旧: target
  destin_mixed_id: string
  candidates: string[]        // 候选源路径列表（含 "!" 表示 delete）
}

export interface PipelineParams {
  database_name: string
  aggregated_rule_set?: Record<string, unknown>
  // Legacy field kept to avoid breaking old call sites during migration.
  kmm_rule_paths?: string[]
  managed_entries?: Record<string, unknown>
  branch_decisions?: Record<string, string>
  dry_run?: boolean
  action_orders?: Record<string, number>
}

export interface DiscoverParams {
  mode: string
  paths: string[] | null
  greedy_parsing: boolean
  database_name: string
}

export interface SseProgress {
  step: string
  finished: number
  total: number
  message: string
}

// ── DataSource types ────────────────────────────────────────────────────────

export type DiscoverMode = 'all' | 'auto' | 'manual'

export interface LibraryRow {
  index: number
  path: string
  gameCount: number
  modCount: number
}

export interface GameRow {
  index: number
  appid: string
  name: string
  basepath: string
  modpath: string
  modCount: number
  libraryIndex: number
  managed: boolean
}

export interface ModRow {
  index: number
  modid: string
  name: string
  appid: string
  path: string
  libraryIndex: number
  gameIndex: number
  managed: boolean
}

export interface DataSourceState {
  discoveryMode: DiscoverMode
  manualPaths: string[]
  workingPathstyle: string
  greedyParsing: boolean
  libraries: LibraryRow[]
  games: GameRow[]
  mods: ModRow[]
  warnings: string[]
  errors: string[]
  libraryVisibility: Record<number, boolean>
  gameVisibility: Record<number, boolean>
  duplicateResolutions: Record<string, number>
  isScanning: boolean
  lastResult: Record<string, unknown> | null
}

// ── Workspace persistence types ─────────────────────────────────────────────

/**
 * Aggregated workspace data stored under a single ``modmanager:workspace`` key.
 *
 * Replaces the previous scattered keys: lastDatabase, decisions:*, results:*,
 * aggregatedRuleSet.
 *
 * @see DESIGN_GUI_WORKSPACE.md
 */
export interface WorkspaceData {
  lastDatabase: string
  perDatabase: Record<string, {
    managedEntries?: Record<string, unknown>
    branchDecisions?: Record<string, string>
    lastComputeSummary: { trees_count: number; mapping_count: number; warnings: string[]; errors: string[]; stats: Record<string, unknown>; inputs_hash: string; timestamp: string } | null
    selectedRulePaths?: string[]
  }>
  // Legacy fields kept for compatibility with older persisted payloads.
  aggregatedRuleSet?: Record<string, unknown> | null
  aggregatedRuleHash?: string
  aggregatedRuleMeta?: {
    output_path: string
    aggregated_hash: string
    aggregated_at: string
    selected_rule_paths: string[]
  } | null
}

import { STR } from '../locales/zh-CN'
import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { streamSse } from '../api/sse'
import { apiPost } from '../api/client'
import { createPersistence } from '../utils/persistence'
import type { SseProgress } from '../api/sse'
import type { TreeNode, Changerequest, ConflictItem, PipelineParams, DiscoverParams } from '../types'

export interface MappingEntry {
  path: string
  mixed_id: string
  hashtype: string
  hashvalue: string
}

export interface PipelineResultData {
  trees: TreeNode[]
  final_mapping: MappingEntry[]
  mapping_result: Record<string, unknown> | null
  stats: Record<string, number> | null
}

export interface RunApiResponse {
  ok: boolean
  data: PipelineResultData | null
  errors: string[]
  warnings: string[]
}

export interface DatabaseSummary {
  libraries: number
  games: number
  mods: number
}

const pers = createPersistence()
const PERSIST_KEY = 'forest-store'

export function generateBackupDir(): string {
  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  return `/tmp/modmanager_backup_${ts}`
}

export const useForestStore = defineStore('forest', () => {
  // ── state ──
  const trees = ref<TreeNode[]>([])
  const finalMapping = ref<MappingEntry[]>([])
  const branchDecisions = ref<Record<string, string>>({})
  const errors = ref<string[]>([])
  const warnings = ref<string[]>([])
  const svgContent = ref<string>('')
  const isRunning = ref(false)
  const progress = ref<SseProgress>({ step: '', finished: 0, total: -1, message: '' })
  const storedMappingResult = ref<Record<string, unknown> | null>(null)

  // ── pipeline form state (persists across page navigation) ──
  const pipelineForm = ref({
    databasePath: '',
    databaseJson: '',
    rulesPaths: '',
    backupDir: '',
    dryRun: true,
    userConfigPath: '',
    workingPathstyle: 'linux',
    greedyParsing: false,
    cachePath: '/tmp/modmanager_database_generated.json',
    discoveryMode: 'auto' as 'auto' | 'manual',
    manualSteamPath: '',
  })

  // ── last successful pipeline params (for recalculate) ──
  const lastSuccessfulParams = ref<PipelineParams | null>(null)

  // ── manual override state ──
  const dbManualOverride = ref(false)

  // ── discovery state ──
  const databaseSummary = ref<DatabaseSummary | null>(null)
  const userConfig = ref<Record<string, unknown> | null>(null)
  const storedDatabase = ref<Record<string, unknown> | null>(null)

  // ── computed: 从 trees 中过滤 pending 状态的树作为冲突列表 ──
  const conflictList = computed<ConflictItem[]>(() => {
    return trees.value
      .filter(t => t.resolved_state === 'pending')
      .map(t => ({
        root_path: t.root_path,
        destin_mixed_id: t.destin_mixed_id || '',
        candidates: t.candidates || [],
      }))
  })

  // ── getters ──
  const unresolvedCount = computed(() =>
    conflictList.value.filter(c => !branchDecisions.value[c.root_path]).length,
  )

  const isClean = computed(() => errors.value.length === 0 && unresolvedCount.value === 0)

  // ── actions ──
  async function runPipeline(params: PipelineParams) {
    isRunning.value = true
    reset()

    await streamSse('/pipeline/run', params, {
      onProgress(p: SseProgress) {
        progress.value = p
      },
      onResult(data: unknown) {
        const result = data as RunApiResponse
        errors.value = result.errors || []
        warnings.value = result.warnings || []
        if (result.data) {
          trees.value = result.data.trees || []
          finalMapping.value = result.data.final_mapping || []
          storedMappingResult.value = result.data.mapping_result
        }
        // Store params for later recalculate
        if (result.ok) {
          lastSuccessfulParams.value = { ...params }
        }
      },
      onError(msg: string) {
        errors.value.push(msg)
      },
    })

    isRunning.value = false
  }

  async function computeOnly(params: PipelineParams) {
    isRunning.value = true
    reset()

    await streamSse('/pipeline/compute', {
      database: params.database,
      kmm_rule_paths: params.kmm_rule_paths,
      user_config_path: params.user_config_path,
      action_orders: params.action_orders,
      branch_decisions: params.branch_decisions,
    }, {
      onProgress(p: SseProgress) {
        progress.value = p
      },
      onResult(data: unknown) {
        const result = data as RunApiResponse
        errors.value = result.errors || []
        warnings.value = result.warnings || []
        if (result.data) {
          trees.value = result.data.trees || []
          finalMapping.value = result.data.final_mapping || []
          storedMappingResult.value = result.data.mapping_result
        }
        // Store params for later recalculate
        if (result.ok) {
          lastSuccessfulParams.value = { ...params }
        }
      },
      onError(msg: string) {
        errors.value.push(msg)
      },
    })

    isRunning.value = false
  }

  async function fetchVisualization(treesOverride?: TreeNode[]) {
    const targetTrees = treesOverride ?? trees.value
    if (targetTrees.length === 0) {
      svgContent.value = ''
      return
    }

    const resp = await apiPost('/pipeline/visualize', {
      trees: targetTrees,
      mapping_result: storedMappingResult.value,
      format: 'svg',
      show_m1_details: true,
    })

    if (resp.ok && resp.data) {
      const data = resp.data as { rendered: string }
      svgContent.value = data.rendered
    }
  }

  async function discoverDatabase() {
    isRunning.value = true
    errors.value = []
    warnings.value = []
    databaseSummary.value = null
    storedDatabase.value = null

    const params: DiscoverParams = {
      mode: pipelineForm.value.discoveryMode,
      paths: pipelineForm.value.discoveryMode === 'manual'
        ? [pipelineForm.value.manualSteamPath]
        : null,
      workingPathstyle: pipelineForm.value.workingPathstyle,
      greedyParsing: pipelineForm.value.greedyParsing,
      cache_path: pipelineForm.value.cachePath,
    }

    await streamSse('/database/generate', params, {
      onProgress(p: SseProgress) {
        progress.value = p
      },
      onResult(data: unknown) {
        const result = data as { ok: boolean; data: Record<string, unknown>; errors?: string[] }
        if (result.ok && result.data) {
          storedDatabase.value = result.data
          databaseSummary.value = {
            libraries: (result.data.steamlib as unknown[])?.length ?? 0,
            games: (result.data.game as unknown[])?.length ?? 0,
            mods: (result.data.mod as unknown[])?.length ?? 0,
          }
        } else if (result.errors?.length) {
          errors.value.push(...result.errors)
        }
      },
      onError(msg: string) {
        errors.value.push(msg)
      },
    })

    isRunning.value = false
  }

  async function loadConfig() {
    // Independent action: discover + save user_config
    try {
      const configResp = await apiPost('/config/discover', {})
      if (configResp.ok && configResp.data) {
        userConfig.value = configResp.data as Record<string, unknown>
        await apiPost('/config/save', {
          config: configResp.data,
          output_path: '/tmp/modmanager_userconfig_generated.json',
        })
      } else {
        // user_config 不存在 → 创建默认值并保存
        const defaultConfig = {
          game_permissions: {},
          sub_permissions: {},
        }
        userConfig.value = defaultConfig
        await apiPost('/config/save', {
          config: defaultConfig,
          output_path: '/tmp/modmanager_userconfig_generated.json',
        })
      }
    } catch {
      errors.value.push(STR.forestStore.failedDiscoverConfig)
    }
  }

  function setDecision(rootPath: string, source: string) {
    branchDecisions.value[rootPath] = source
  }

  function clearDecisions() {
    branchDecisions.value = {}
  }

  function reset() {
    // ── 输出字段：每次新计算时清空 ──
    trees.value = []
    finalMapping.value = []
    // branchDecisions — 保留（用户决策跨刷新/切换页面持久化，与 lastSuccessfulParams 同级）
    errors.value = []
    warnings.value = []
    svgContent.value = ''
    progress.value = { step: '', finished: 0, total: -1, message: '' }
    storedMappingResult.value = null
    lastSuccessfulParams.value = null

    // ── 输入字段：保留用户/数据源配置 ──
    // storedDatabase — 保留（从 DataSource 传入）
    // pipelineForm — 保留（用户填的参数）
    // dbManualOverride — 保留（锁定状态）
    // userConfig — 保留
    // databaseSummary — 保留
  }

  // ── persistence ──
  function savePersistentState() {
    pers.save(PERSIST_KEY, {
      storedDatabase: storedDatabase.value,
      pipelineForm: pipelineForm.value,
      dbManualOverride: dbManualOverride.value,
      databaseSummary: databaseSummary.value,
      userConfig: userConfig.value,
    })
  }

  function loadPersistentState() {
    const saved = pers.load<{
      storedDatabase: Record<string, unknown> | null;
      pipelineForm: typeof pipelineForm.value;
      dbManualOverride: boolean;
      databaseSummary: any;
      userConfig: Record<string, unknown> | null;
    }>(PERSIST_KEY)
    if (saved) {
      if (saved.storedDatabase) storedDatabase.value = saved.storedDatabase
      if (saved.pipelineForm) pipelineForm.value = saved.pipelineForm
      if (saved.dbManualOverride !== undefined) dbManualOverride.value = saved.dbManualOverride
      if (saved.databaseSummary) databaseSummary.value = saved.databaseSummary
      if (saved.userConfig) userConfig.value = saved.userConfig
    }
  }

  // Restore persisted state on store creation
  loadPersistentState()

  // Auto-persist when key state fields change
  watch(
    [storedDatabase, pipelineForm, dbManualOverride, databaseSummary, userConfig],
    () => savePersistentState(),
    { deep: true },
  )

  return {
    trees,
    finalMapping,
    conflictList,
    branchDecisions,
    errors,
    warnings,
    svgContent,
    isRunning,
    progress,
    databaseSummary,
    userConfig,
    storedDatabase,
    storedMappingResult,
    dbManualOverride,
    lastSuccessfulParams,
    pipelineForm,
    unresolvedCount,
    isClean,
    runPipeline,
    computeOnly,
    fetchVisualization,
    discoverDatabase,
    loadConfig,
    setDecision,
    clearDecisions,
    reset,
  }
})

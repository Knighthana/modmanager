import { STR } from '../locales/zh-CN'
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { streamSse } from '../api/transport'
import { apiPost } from '../api/transport'
// persistence no longer needed in forest store
import type { SseProgress } from '../api/transport'
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

export const useForestStore = defineStore('forest', () => {
  // ── state ──
  const aggregatedRuleSet = ref<Record<string, unknown> | null>(null)
  const trees = ref<TreeNode[]>([])
  const finalMapping = ref<MappingEntry[]>([])
  const branchDecisions = ref<Record<string, string>>({})
  const errors = ref<string[]>([])
  const warnings = ref<string[]>([])
  const svgContent = ref<string>('')
  const isRunning = ref(false)
  const progress = ref<SseProgress>({ step: '', finished: 0, total: -1, message: '' })
  const storedMappingResult = ref<Record<string, unknown> | null>(null)
  const stats = ref<Record<string, number>>({})

  // ── pipeline form state (persists across page navigation) ──
  const pipelineForm = ref({
    databaseName: 'default',
    rulesPaths: '',
    dryRun: true,
    greedyParsing: false,
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

    const resolvedRuleSet = params.aggregated_rule_set ?? aggregatedRuleSet.value ?? undefined

    await streamSse('/pipeline/run', {
      database_name: params.database_name,
      aggregated_rule_set: resolvedRuleSet,
      managed_entries: params.managed_entries,
      branch_decisions: params.branch_decisions,
      dry_run: params.dry_run,
      action_orders: params.action_orders,
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
          stats.value = result.data.stats ?? {}
        }
        // Store params for later recalculate
        if (result.ok) {
          lastSuccessfulParams.value = {
            ...params,
            aggregated_rule_set: resolvedRuleSet,
          }
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

    const resolvedRuleSet = params.aggregated_rule_set ?? aggregatedRuleSet.value ?? undefined

    await streamSse('/pipeline/compute', {
      database_name: params.database_name,
      aggregated_rule_set: resolvedRuleSet,
      managed_entries: params.managed_entries,
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
          stats.value = result.data.stats ?? {}
        }
        // Store params for later recalculate
        if (result.ok) {
          lastSuccessfulParams.value = {
            ...params,
            aggregated_rule_set: resolvedRuleSet,
          }
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

    const params: DiscoverParams = {
      mode: pipelineForm.value.discoveryMode,
      paths: pipelineForm.value.discoveryMode === 'manual'
        ? [pipelineForm.value.manualSteamPath]
        : null,
      greedy_parsing: pipelineForm.value.greedyParsing,
      database_name: pipelineForm.value.databaseName,
    }

    await streamSse('/database/generate', params, {
      onProgress(p: SseProgress) {
        progress.value = p
      },
      onResult(data: unknown) {
        const result = data as { ok: boolean; data: Record<string, unknown>; errors?: string[] }
        if (result.ok && result.data) {
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
        const data = configResp.data as Record<string, unknown>
        const config = data.config as Record<string, unknown>
        const configIndex = data.config_index as string
        userConfig.value = config
        await apiPost('/config/save', {
          config_index: configIndex,
          config,
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
    // branchDecisions — 保留（用户决策跨刷新/切换页面持久化，通过后端 workspace API）
    errors.value = []
    warnings.value = []
    svgContent.value = ''
    progress.value = { step: '', finished: 0, total: -1, message: '' }
    storedMappingResult.value = null
    stats.value = {}
    lastSuccessfulParams.value = null

    // ── 输入字段：保留用户/数据源配置 ──
    // pipelineForm — 保留（用户填的参数）
    // dbManualOverride — 保留（锁定状态）
    // userConfig — 保留
    // databaseSummary — 保留
  }

  return {
    aggregatedRuleSet,
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
    storedMappingResult,
    stats,
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

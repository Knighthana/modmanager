import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { streamSse } from '../api/sse'
import { apiPost } from '../api/client'
import type { SseProgress } from '../api/sse'
import type { TreeNode, Changerequest, ConflictItem, PipelineParams } from '../types'

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

export interface DiscoverParams {
  mode: string
  paths: string[] | null
  workingPathstyle: string
  greedyParsing: boolean
  cachePath: string | null
}

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
  })

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
      },
      onError(msg: string) {
        errors.value.push(msg)
      },
    })

    isRunning.value = false
  }

  async function fetchVisualization() {
    if (trees.value.length === 0) {
      svgContent.value = ''
      return
    }

    const resp = await apiPost('/pipeline/visualize', {
      trees: trees.value,
      mapping_result: storedMappingResult.value,
      format: 'svg',
      show_m1_details: true,
    })

    if (resp.ok && resp.data) {
      const data = resp.data as { rendered: string }
      svgContent.value = data.rendered
    }
  }

  async function discoverDatabase(params: DiscoverParams) {
    isRunning.value = true
    errors.value = []
    warnings.value = []
    databaseSummary.value = null
    userConfig.value = null
    storedDatabase.value = null

    let discoverOk = false

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
            mods: (result.data.dommod as unknown[])?.length ?? 0,
          }
          discoverOk = true
        } else if (result.errors?.length) {
          errors.value.push(...result.errors)
        }
      },
      onError(msg: string) {
        errors.value.push(msg)
      },
    })

    // After SSE completes, fetch and save user_config
    if (discoverOk) {
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
        errors.value.push('Failed to discover or save user_config')
      }
    }

    isRunning.value = false
  }

  function setDecision(rootPath: string, source: string) {
    branchDecisions.value[rootPath] = source
  }

  function clearDecisions() {
    branchDecisions.value = {}
  }

  function reset() {
    trees.value = []
    finalMapping.value = []
    branchDecisions.value = {}
    errors.value = []
    warnings.value = []
    svgContent.value = ''
    progress.value = { step: '', finished: 0, total: -1, message: '' }
    databaseSummary.value = null
    userConfig.value = null
    storedDatabase.value = null
    storedMappingResult.value = null
    pipelineForm.value = {
      databasePath: '',
      databaseJson: '',
      rulesPaths: '',
      backupDir: '',
      dryRun: true,
      userConfigPath: '',
      workingPathstyle: 'linux',
      greedyParsing: false,
      cachePath: '/tmp/modmanager_database_generated.json',
    }
  }

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
    pipelineForm,
    unresolvedCount,
    isClean,
    runPipeline,
    computeOnly,
    fetchVisualization,
    discoverDatabase,
    setDecision,
    clearDecisions,
    reset,
  }
})

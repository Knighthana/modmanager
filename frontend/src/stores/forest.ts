import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { streamSse } from '../api/sse'
import type { SseProgress } from '../api/sse'

export interface ForestNode {
  path: string
  destin_mixed_id: string
  changerequest: Changerequest[]
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
  mixed_id: string
  hashtype: string
  hashvalue: string
}

export interface ConflictItem {
  target: string
  destin_mixed_id: string
  candidates: string[]
}

export interface PipelineParams {
  database: Record<string, unknown>
  kmm_rule_paths: string[]
  user_config_path: string
  backup_dir: string
  dry_run: boolean
  action_orders?: Record<string, number>
  branch_decisions?: Record<string, string>
}

export interface PipelineResultData {
  forest: ForestNode[]
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

function extractConflicts(forest: ForestNode[]): ConflictItem[] {
  return forest
    .filter(n => n.warning === 'W_FOREST_BRANCHING')
    .map(n => ({
      target: n.path,
      destin_mixed_id: n.destin_mixed_id || '',
      candidates: n.candidates || [],
    }))
}

export const useForestStore = defineStore('forest', () => {
  // ── state ──
  const forest = ref<ForestNode[]>([])
  const finalMapping = ref<MappingEntry[]>([])
  const conflictList = ref<ConflictItem[]>([])
  const branchDecisions = ref<Record<string, string>>({})
  const errors = ref<string[]>([])
  const warnings = ref<string[]>([])
  const svgContent = ref<string>('')
  const isRunning = ref(false)
  const progress = ref<SseProgress>({ step: '', finished: 0, total: -1, message: '' })

  // ── getters ──
  const unresolvedCount = computed(() =>
    conflictList.value.filter(c => !branchDecisions.value[c.target]).length,
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
          forest.value = result.data.forest || []
          finalMapping.value = result.data.final_mapping || []
          conflictList.value = extractConflicts(result.data.forest || [])
        }
      },
      onError(msg: string) {
        errors.value.push(msg)
      },
    })

    isRunning.value = false
  }

  function setDecision(target: string, source: string) {
    branchDecisions.value[target] = source
  }

  function clearDecisions() {
    branchDecisions.value = {}
  }

  function reset() {
    forest.value = []
    finalMapping.value = []
    conflictList.value = []
    branchDecisions.value = {}
    errors.value = []
    warnings.value = []
    svgContent.value = ''
    progress.value = { step: '', finished: 0, total: -1, message: '' }
  }

  return {
    forest,
    finalMapping,
    conflictList,
    branchDecisions,
    errors,
    warnings,
    svgContent,
    isRunning,
    progress,
    unresolvedCount,
    isClean,
    runPipeline,
    setDecision,
    clearDecisions,
    reset,
  }
})

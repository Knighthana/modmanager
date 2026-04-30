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
  request: Changerequest
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

export interface SseProgress {
  step: string
  finished: number
  total: number
  message: string
}

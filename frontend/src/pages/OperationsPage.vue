<template>
  <div>
    <h2>{{ STR.operationsPage.title }}</h2>

    <!-- Loading state -->
    <div v-if="loading" style="text-align: center; padding: 40px;">
      <p style="color: var(--el-text-color-secondary);">加载中...</p>
    </div>

    <!-- Empty state: 无计算结果 -->
    <el-empty
      v-else-if="!hasResults"
      :description="STR.operationsPage.emptyState"
    />

    <!-- Main content -->
    <template v-else>
      <!-- 映射摘要 -->
      <el-card shadow="never">
        <template #header>
          {{ STR.operationsPage.summaryTitle }}
        </template>
        <el-descriptions :column="4" border>
          <el-descriptions-item :label="STR.operationsPage.treesCount">
            {{ wsResults.trees_count }}
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.mappingCount">
            {{ wsResults.mapping_count }}
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.statAdded">
            {{ getStat('added') }}
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.statOverwritten">
            {{ getStat('overwritten') }}
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.statDeleted">
            {{ getStat('deleted') }}
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.warnings">
            <el-badge :value="wsResults.warnings.length" type="warning">
              <span style="padding: 0 4px;">{{ wsResults.warnings.length }}</span>
            </el-badge>
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.errors">
            <el-badge :value="wsResults.errors.length" type="danger">
              <span style="padding: 0 4px;">{{ wsResults.errors.length }}</span>
            </el-badge>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 执行选项 -->
      <el-card shadow="never" style="margin-top: 16px;">
        <template #header>
          {{ STR.operationsPage.optionsTitle }}
        </template>
        <el-form label-width="0">
          <el-form-item>
            <el-switch
              v-model="dryRun"
              :active-text="STR.operationsPage.dryRunLabel"
            />
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 操作按钮 -->
      <div style="display: flex; gap: 12px; margin-top: 16px;">
        <el-button
          type="warning"
          :disabled="operating !== null"
          @click="confirmBackup"
        >
          {{ STR.operationsPage.backupBtn }}
        </el-button>
        <el-button
          type="primary"
          :disabled="operating !== null"
          @click="confirmApply"
        >
          {{ STR.operationsPage.applyBtn }}
        </el-button>
        <el-button
          type="danger"
          :disabled="operating !== null"
          @click="confirmRestore"
        >
          {{ STR.operationsPage.restoreBtn }}
        </el-button>
      </div>

      <!-- 进度条 -->
      <el-card v-if="operating !== null" shadow="never" style="margin-top: 16px;">
        <template #header>
          {{ operationLabel(operating) }}
        </template>
        <el-progress :percentage="progressPct" :stroke-width="16" />
        <p style="margin-top: 8px; font-size: 13px; color: var(--el-text-color-secondary);">
          {{ progress.message || '处理中...' }}
        </p>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { streamSse, type SseProgress } from '../api/sse'
import { useForestStore } from '../stores/forest'
import { generateBackupDir } from '../stores/forest'
import { STR } from '../locales/zh-CN'

// ── types ──────────────────────────────────────────────────────────────

interface WorkspaceStatus {
  results: {
    last_compute: {
      trees_count: number
      mapping_count: number
      warnings: string[]
      errors: string[]
      stats: Record<string, number>
      inputs_hash: string
      timestamp: string | null
    } | null
  }
  inputs: {
    database_path: string
    rule_paths: string[]
    aggregated_rule_path: string
    user_config_path: string
    discovery_mode: string
    discovery_manual_paths: string[]
  }
}

// ── state ──────────────────────────────────────────────────────────────

const store = useForestStore()

const loading = ref(true)
const wsStatus = ref<WorkspaceStatus | null>(null)
const dryRun = ref(true)
const operating = ref<string | null>(null) // 'backup' | 'apply' | 'restore'
const progress = ref<SseProgress>({ step: '', finished: 0, total: -1, message: '' })

// ── computed ───────────────────────────────────────────────────────────

/** 是否有有效的计算结果 */
const hasResults = computed(() => {
  const rc = wsStatus.value?.results?.last_compute
  return rc != null && rc.trees_count > 0
})

/** workspace results 快捷引用 */
const wsResults = computed(() => {
  return wsStatus.value?.results?.last_compute ?? {
    trees_count: 0,
    mapping_count: 0,
    warnings: [],
    errors: [],
    stats: {},
    inputs_hash: '',
    timestamp: null,
  }
})

/** workspace inputs 快捷引用 */
const wsInputs = computed(() => {
  return wsStatus.value?.inputs ?? {
    database_path: '',
    rule_paths: [],
    aggregated_rule_path: '',
    user_config_path: '',
    discovery_mode: 'auto',
    discovery_manual_paths: [],
  }
})

/** 进度百分比 */
const progressPct = computed(() => {
  const { finished, total } = progress.value
  if (total <= 0) return 0
  return Math.round((finished / total) * 100)
})

/** 操作显示名称 */
function operationLabel(op: string): string {
  const labels: Record<string, string> = {
    backup: STR.operationsPage.backupBtn,
    apply: STR.operationsPage.applyBtn,
    restore: STR.operationsPage.restoreBtn,
  }
  return labels[op] || op
}

// ── helpers ────────────────────────────────────────────────────────────

function getStat(key: string): number {
  return wsResults.value.stats?.[key] ?? 0
}

// ── onMounted: 加载 workspace 状态 ──────────────────────────────────────

onMounted(async () => {
  try {
    const res = await fetch('/api/workspace/status')
    const json = await res.json()
    if (json.ok && json.data) {
      wsStatus.value = json.data as WorkspaceStatus
    }
  } catch {
    // workspace not available — empty state will be shown
  } finally {
    loading.value = false
  }
})

// ── 操作确认 & 执行 ────────────────────────────────────────────────────

async function confirmBackup() {
  try {
    await ElMessageBox.confirm(
      STR.operationsPage.confirmBackupMsg,
      STR.operationsPage.confirmBackupTitle,
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' },
    )
    await doBackup()
  } catch {
    // cancelled by user
  }
}

async function confirmApply() {
  try {
    await ElMessageBox.confirm(
      STR.operationsPage.confirmApplyMsg,
      STR.operationsPage.confirmApplyTitle,
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'primary' },
    )
    await doApply()
  } catch {
    // cancelled by user
  }
}

async function confirmRestore() {
  try {
    await ElMessageBox.confirm(
      STR.operationsPage.confirmRestoreMsg,
      STR.operationsPage.confirmRestoreTitle,
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'error' },
    )
    await doRestore()
  } catch {
    // cancelled by user
  }
}

/** 差异备份 */
async function doBackup() {
  operating.value = 'backup'
  progress.value = { step: 'backup', finished: 0, total: -1, message: '准备中...' }

  const backupDir = store.pipelineForm.backupDir || generateBackupDir()

  await streamSse('/pipeline/backup', {
    mapping_result: store.storedMappingResult,
    backup_dir: backupDir,
    database: wsInputs.value.database_path,
    user_config_path: wsInputs.value.user_config_path,
  }, {
    onProgress(p: SseProgress) {
      progress.value = p
    },
    onResult() {
      ElMessage.success(STR.operationsPage.operationSuccess)
      operating.value = null
    },
    onError(msg: string) {
      ElMessage.error(`${STR.operationsPage.operationFailed}: ${msg}`)
      operating.value = null
    },
  })
}

/** 应用映射 */
async function doApply() {
  operating.value = 'apply'
  progress.value = { step: 'apply', finished: 0, total: -1, message: '准备中...' }

  const backupDir = store.pipelineForm.backupDir || generateBackupDir()

  await streamSse('/pipeline/apply', {
    final_mapping: store.finalMapping,
    backup_dir: backupDir,
    dry_run: dryRun.value,
  }, {
    onProgress(p: SseProgress) {
      progress.value = p
    },
    onResult() {
      ElMessage.success(STR.operationsPage.operationSuccess)
      operating.value = null
    },
    onError(msg: string) {
      ElMessage.error(`${STR.operationsPage.operationFailed}: ${msg}`)
      operating.value = null
    },
  })
}

/** 恢复备份 */
async function doRestore() {
  operating.value = 'restore'
  progress.value = { step: 'restore', finished: 0, total: -1, message: '准备中...' }

  const backupDir = store.pipelineForm.backupDir || generateBackupDir()

  await streamSse('/pipeline/restore', {
    backup_dir: backupDir,
    target_files: null, // restore all files
  }, {
    onProgress(p: SseProgress) {
      progress.value = p
    },
    onResult() {
      ElMessage.success(STR.operationsPage.operationSuccess)
      operating.value = null
    },
    onError(msg: string) {
      ElMessage.error(`${STR.operationsPage.operationFailed}: ${msg}`)
      operating.value = null
    },
  })
}
</script>

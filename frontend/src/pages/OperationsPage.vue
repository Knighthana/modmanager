<template>
  <div class="operations-page gui-page">
    <h2>{{ STR.operationsPage.title }}</h2>

    <!-- DatabaseSelector -->
    <div style="margin-bottom: 16px;">
      <DatabaseSelector ref="databaseSelectorRef" />
    </div>

    <!-- Empty state: 无计算结果 -->
    <el-empty
      v-if="!hasResults"
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
            {{ localResults.trees_count }}
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.mappingCount">
            {{ localResults.mapping_count }}
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
            <el-badge :value="localResults.warnings.length" type="warning">
              <span style="padding: 0 4px;">{{ localResults.warnings.length }}</span>
            </el-badge>
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.errors">
            <el-badge :value="localResults.errors.length" type="danger">
              <span style="padding: 0 4px;">{{ localResults.errors.length }}</span>
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
import { ref, computed } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { streamSse, type SseProgress } from '../api/transport'
import { useForestStore } from '../stores/forest'
import { generateBackupDir } from '../stores/forest'
// workspace state now from forest store
import DatabaseSelector from '../components/DatabaseSelector.vue'
import { STR } from '../locales/zh-CN'

// ── types ──────────────────────────────────────────────────────────────

interface LocalResults {
  trees_count: number
  mapping_count: number
  warnings: string[]
  errors: string[]
  stats: Record<string, unknown>
  inputs_hash?: string
  timestamp?: string
}

// ── state ──────────────────────────────────────────────────────────────

const store = useForestStore()

const databaseSelectorRef = ref<InstanceType<typeof DatabaseSelector> | null>(null)
const dryRun = ref(true)
const operating = ref<string | null>(null) // 'backup' | 'apply' | 'restore'
const progress = ref<SseProgress>({ step: '', finished: 0, total: -1, message: '' })

// ── computed ───────────────────────────────────────────────────────────

const selectedDb = computed(() => databaseSelectorRef.value?.selectedDatabase ?? 'default')

/** 是否有有效的计算结果 */
const localResults = computed<LocalResults>(() => ({
  trees_count: store.trees.length,
  mapping_count: store.finalMapping.length,
  warnings: store.warnings,
  errors: store.errors,
  stats: store.stats,
}))

const hasResults = computed(() => localResults.value.trees_count > 0)

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
  return (localResults.value.stats?.[key] as number) ?? 0
}

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
      { confirmButtonType: 'danger', confirmButtonText: '确认', cancelButtonText: '取消' },
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
    database_name: selectedDb.value,
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
    database_name: selectedDb.value,
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

<style scoped>
.operations-page {
  margin: 0 auto;
  padding: 16px 24px;
}
</style>

<template>
  <div class="operations-page gui-page">
    <h2>{{ STR.operationsPage.title }}</h2>

    <!-- Loading state -->
    <div v-if="loadState === 'loading'" style="text-align: center; padding: 60px 0;">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p style="margin-top: 12px; color: var(--el-text-color-secondary); font-size: 14px;">
        正在加载工作区映射数据...
      </p>
    </div>

    <!-- Error state -->
    <el-empty
      v-else-if="loadState === 'error'"
      :description="loadError || '数据加载失败'"
    >
      <el-button @click="loadMappingFromWorkspace">重试</el-button>
    </el-empty>

    <!-- Empty state: 无计算结果 -->
    <el-empty
      v-else-if="!hasResults"
      :description="STR.operationsPage.emptyState"
    >
      <el-button type="primary" @click="router.push(`/workspace/${workspaceId}/compute`)">
        前往计算准备
      </el-button>
    </el-empty>

    <!-- Main content -->
    <template v-else>
      <!-- 映射摘要 -->
      <el-card shadow="never">
        <template #header>
          {{ STR.operationsPage.summaryTitle }}
        </template>
        <el-descriptions class="summary-table" :column="4" border size="small">
          <el-descriptions-item :label="STR.operationsPage.mappingCount">
            {{ localResults.mapping_count }}
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.statAdded">
            {{ mappingStats.added }}
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.statOverwritten">
            {{ mappingStats.overwritten }}
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.statDeleted">
            {{ mappingStats.deleted }}
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.mappingWarnings">
            <template v-if="localResults.warnings.length > 0">
              <el-badge :value="localResults.warnings.length" type="warning">
                <span style="padding: 0 4px; cursor: pointer;" @click="showMappingWarningsDialog = true">{{ localResults.warnings.length }}</span>
              </el-badge>
            </template>
            <span v-else style="padding: 0 4px; color: var(--el-text-color-placeholder);">0</span>
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.mappingErrors">
            <template v-if="localResults.errors.length > 0">
              <el-badge :value="localResults.errors.length" type="danger">
                <span style="padding: 0 4px; cursor: pointer;" @click="showMappingErrorsDialog = true">{{ localResults.errors.length }}</span>
              </el-badge>
            </template>
            <span v-else style="padding: 0 4px; color: var(--el-text-color-placeholder);">0</span>
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.operationWarnings">
            <template v-if="operationWarnings.length > 0">
              <el-badge :value="operationWarnings.length" type="warning">
                <span style="padding: 0 4px; cursor: pointer;" @click="quickLocateFromSummary">{{ operationWarnings.length }}</span>
              </el-badge>
            </template>
            <span v-else style="padding: 0 4px; color: var(--el-text-color-placeholder);">0</span>
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.operationErrors">
            <template v-if="operationErrors.length > 0">
              <el-badge :value="operationErrors.length" type="danger">
                <span style="padding: 0 4px; cursor: pointer;" @click="quickLocateErrorFromSummary">{{ operationErrors.length }}</span>
              </el-badge>
            </template>
            <span v-else style="padding: 0 4px; color: var(--el-text-color-placeholder);">0</span>
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
        <el-progress :percentage="progressPct" :stroke-width="16" :format="() => progressText" />
        <p style="margin-top: 8px; font-size: 13px; color: var(--el-text-color-secondary);">
          {{ progress.message || '处理中...' }}
        </p>
      </el-card>

      <!-- 最近一次 apply 诊断摘要 -->
      <el-card id="apply-diagnostics-card" v-if="applyDiagnostics !== null" shadow="never" style="margin-top: 16px;">
        <template #header>
          {{ STR.operationsPage.applyDiagnosticsTitle }}
          <el-button size="small" style="float: right;" @click="applyDiagnostics = null">{{ STR.operationsPage.clearDiagnostics }}</el-button>
        </template>
        <el-descriptions :column="4" border size="small">
          <el-descriptions-item :label="STR.operationsPage.diagTotalDirs">
            {{ applyDiagnostics.total_backup_dirs ?? 0 }}
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.diagProcessedDirs">
            {{ applyDiagnostics.processed_dirs ?? 0 }}
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.diagGateFailedDirs">
            {{ gateFailedDirs.length }}
          </el-descriptions-item>
          <el-descriptions-item :label="STR.operationsPage.diagNoMatchedDirs">
            {{ noMatchedDirs.length }}
          </el-descriptions-item>
        </el-descriptions>
        <el-alert
          v-if="gateFailedDirs.length > 0 || noMatchedDirs.length > 0"
          style="margin-top: 12px;"
          type="warning"
          :closable="false"
          :title="diagnosticsHint"
        />
        <el-collapse
          v-if="gateFailedDirs.length > 0 || noMatchedDirs.length > 0"
          v-model="diagExpandedPanels"
          style="margin-top: 12px;"
        >
          <el-collapse-item
            v-if="gateFailedDirs.length > 0"
            :title="`${STR.operationsPage.diagGateFailedListTitle} (${gateFailedDirs.length})`"
            name="gate-failed"
          >
            <el-table
              :data="gateFailedRows"
              :row-class-name="diagRowClassName"
              size="small"
              max-height="220"
              border
            >
              <el-table-column prop="index" label="#" width="56" />
              <el-table-column prop="path" :label="STR.operationsPage.diagDirPathLabel" min-width="380" />
              <el-table-column :label="STR.operationsPage.diagActions" width="120" align="center">
                <template #default="{ row }">
                  <el-button size="small" @click="copyDiagPath(String(row.path))">{{ STR.operationsPage.copyPath }}</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-collapse-item>

          <el-collapse-item
            v-if="noMatchedDirs.length > 0"
            :title="`${STR.operationsPage.diagNoMatchedListTitle} (${noMatchedDirs.length})`"
            name="no-matched"
          >
            <el-table
              :data="noMatchedRows"
              :row-class-name="diagRowClassName"
              size="small"
              max-height="220"
              border
            >
              <el-table-column prop="index" label="#" width="56" />
              <el-table-column prop="path" :label="STR.operationsPage.diagDirPathLabel" min-width="380" />
              <el-table-column :label="STR.operationsPage.diagActions" width="120" align="center">
                <template #default="{ row }">
                  <el-button size="small" @click="copyDiagPath(String(row.path))">{{ STR.operationsPage.copyPath }}</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-collapse-item>
        </el-collapse>
      </el-card>

      <!-- dry-run 文件列表 -->
      <el-card v-if="dryRunEntries.length > 0" shadow="never" style="margin-top: 16px;">
        <template #header>
          <span>[dry-run] {{ operationLabel(dryRunOperation) }} — 共 {{ dryRunEntries.length }} 个文件</span>
          <el-button size="small" style="float: right;" @click="dryRunEntries = []">清除列表</el-button>
        </template>
        <el-table :data="dryRunEntries" size="small" max-height="400" border stripe>
          <el-table-column label="操作" width="80" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.action === 'delete'" type="danger" size="small">删除</el-tag>
              <el-tag v-else-if="row.action === 'create'" type="success" size="small">创建</el-tag>
              <el-tag v-else-if="row.action === 'replace'" type="warning" size="small">替换</el-tag>
              <el-tag v-else-if="row.action === 'copy'" type="info" size="small">拷贝</el-tag>
              <el-tag v-else size="small">{{ row.action || '—' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="80" align="center">
            <template #default="{ row }">{{ row.is_dir ? '目录' : '文件' }}</template>
          </el-table-column>
          <el-table-column :label="dryRunOperation === 'backup' ? '备份位置' : '目标路径'" min-width="300">
            <template #default="{ row }">{{ row.backup_path || row.target || row.path }}</template>
          </el-table-column>
          <el-table-column v-if="dryRunOperation !== 'restore'" :label="dryRunOperation === 'backup' ? '源路径' : '源路径'" min-width="200">
            <template #default="{ row }">{{ row.source || row.path }}</template>
          </el-table-column>
          <el-table-column label="大小" width="100" align="right">
            <template #default="{ row }">{{ formatSize(row.size as number) }}</template>
          </el-table-column>
          <el-table-column label="修改时间" width="180">
            <template #default="{ row }">{{ formatMtime(row.mtime as number) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 映射警告 dialog -->
      <el-dialog v-model="showMappingWarningsDialog" title="映射警告详情" width="600px">
        <div v-if="localResults.warnings.length === 0" style="color: var(--el-text-color-placeholder);">无警告</div>
        <el-table v-else :data="localResults.warnings.map((w, i) => ({ index: i + 1, message: w }))" size="small" max-height="400">
          <el-table-column prop="index" label="#" width="50" />
          <el-table-column prop="message" label="警告内容" />
        </el-table>
        <template #footer>
          <el-button @click="showMappingWarningsDialog = false">关闭</el-button>
        </template>
      </el-dialog>

      <!-- 映射错误 dialog -->
      <el-dialog v-model="showMappingErrorsDialog" title="映射错误详情" width="600px">
        <div v-if="localResults.errors.length === 0" style="color: var(--el-text-color-placeholder);">无错误</div>
        <el-table v-else :data="localResults.errors.map((e, i) => ({ index: i + 1, message: e }))" size="small" max-height="400">
          <el-table-column prop="index" label="#" width="50" />
          <el-table-column prop="message" label="错误内容" />
        </el-table>
        <template #footer>
          <el-button @click="showMappingErrorsDialog = false">关闭</el-button>
        </template>
      </el-dialog>

      <!-- 操作警告 dialog -->
      <el-dialog v-model="showOpWarningsDialog" title="操作警告详情" width="600px">
        <div v-if="operationWarnings.length === 0" style="color: var(--el-text-color-placeholder);">无警告</div>
        <el-table v-else :data="operationWarningRows" size="small" max-height="400">
          <el-table-column prop="index" label="#" width="50" />
          <el-table-column prop="message" label="警告内容" min-width="360" />
          <el-table-column :label="STR.operationsPage.diagActions" width="100" align="center">
            <template #default="{ row }">
              <el-button
                v-if="row.canLocate"
                size="small"
                @click="locateWarning(row)"
              >
                {{ STR.operationsPage.locateWarning }}
              </el-button>
              <span v-else style="color: var(--el-text-color-placeholder);">-</span>
            </template>
          </el-table-column>
        </el-table>
        <template #footer>
          <el-button @click="showOpWarningsDialog = false">关闭</el-button>
        </template>
      </el-dialog>

      <!-- 操作错误 dialog -->
      <el-dialog v-model="showOpErrorsDialog" title="操作错误详情" width="600px">
        <div v-if="operationErrors.length === 0" style="color: var(--el-text-color-placeholder);">无错误</div>
        <template v-else>
          <div style="margin-bottom: 12px; display: flex; gap: 8px; flex-wrap: wrap;">
            <el-tag
              :type="selectedErrorCode === '' ? 'danger' : 'info'"
              style="cursor: pointer;"
              @click="selectedErrorCode = ''"
            >
              {{ STR.operationsPage.errorGroupAll }} ({{ operationErrorRows.length }})
            </el-tag>
            <el-tag
              v-for="group in operationErrorGroups"
              :key="group.code"
              :type="selectedErrorCode === group.code ? 'danger' : 'info'"
              style="cursor: pointer;"
              @click="selectedErrorCode = group.code"
            >
              {{ group.code }} ({{ group.count }})
            </el-tag>
          </div>
          <el-table :data="filteredOperationErrorRows" size="small" max-height="400">
            <el-table-column prop="index" label="#" width="50" />
            <el-table-column prop="code" :label="STR.operationsPage.errorGroupCode" width="170" />
            <el-table-column prop="path" :label="STR.operationsPage.errorGroupPath" min-width="180" />
            <el-table-column :label="STR.operationsPage.diagActions" width="100" align="center">
              <template #default="{ row }">
                <el-button
                  v-if="hasErrorPath(row)"
                  size="small"
                  @click="copyDiagPath(String(row.path))"
                >
                  {{ STR.operationsPage.copyPath }}
                </el-button>
                <span v-else style="color: var(--el-text-color-placeholder);">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="错误内容" min-width="240" />
          </el-table>
        </template>
        <template #footer>
          <el-button @click="showOpErrorsDialog = false">关闭</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { streamSse, apiGet, type SseProgress } from '../api/transport'
import { useForestStore } from '../stores/forest'
import { useAppStore } from '../stores/app'
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

// ── router & stores ────────────────────────────────────────────────────

const router = useRouter()
const route = useRoute()
const store = useForestStore()
const appStore = useAppStore()

// ── state ──────────────────────────────────────────────────────────────

const workspaceId = computed(() => route.params.workspaceId as string)
const dryRun = ref(true)
const operating = ref<string | null>(null) // 'backup' | 'apply' | 'restore'
const progress = ref<SseProgress>({ step: '', finished: 0, total: -1, message: '' })
const loadState = ref<'loading' | 'loaded' | 'error'>('loading')
const loadError = ref('')
const showMappingWarningsDialog = ref(false)
const showMappingErrorsDialog = ref(false)
const showOpWarningsDialog = ref(false)
const showOpErrorsDialog = ref(false)
/** 最近一次操作产生的警告/错误，持久显示直到下次操作覆盖 */
const operationWarnings = ref<string[]>([])
const operationErrors = ref<string[]>([])
const selectedErrorCode = ref('')
/** dry-run 结果文件列表，操作完成后显示在页面下方 */
const dryRunEntries = ref<Array<Record<string, unknown>>>([])
const dryRunOperation = ref('') // 'backup' | 'apply' | 'restore'
/** 最近一次 apply 的结构化诊断 */
const applyDiagnostics = ref<Record<string, unknown> | null>(null)
const diagExpandedPanels = ref<string[]>([])
const diagFocusedPath = ref('')

// ── computed ───────────────────────────────────────────────────────────

/** 是否有有效的计算结果 */
const localResults = ref<LocalResults>({
  trees_count: 0,
  mapping_count: 0,
  warnings: [],
  errors: [],
  stats: {},
})

const hasResults = computed(
  () => localResults.value.trees_count > 0 || localResults.value.mapping_count > 0,
)

/** 从映射数据统计新增/覆盖/删除数量 */
const mappingStats = computed(() => {
  const stats = { added: 0, overwritten: 0, deleted: 0 }
  // Use the rawMapping data that populateResults stored
  const mapping = (localResults.value as any)._rawMapping as any[] | undefined
  if (!mapping) return stats
  for (const entry of mapping) {
    const action = entry?.request?.action
    if (action === 'create') stats.added++
    else if (action === 'replace') stats.overwritten++
    else if (action === 'delete') stats.deleted++
  }
  return stats
})

/** 进度百分比 */
const progressPct = computed(() => {
  const { finished, total } = progress.value
  if (total <= 0) return 0
  return Math.round((finished / total) * 100)
})

/** 进度文本 {finish}/{total} */
const progressText = computed(() => {
  const { finished, total } = progress.value
  return `${finished ?? 0}/${total ?? 1}`
})

const gateFailedDirs = computed(() => {
  const raw = applyDiagnostics.value?.gate_failed_dirs
  return Array.isArray(raw) ? raw : []
})

const noMatchedDirs = computed(() => {
  const raw = applyDiagnostics.value?.no_matched_entry_dirs
  return Array.isArray(raw) ? raw : []
})

const gateFailedRows = computed(() => gateFailedDirs.value.map((path, i) => ({
  index: i + 1,
  path: String(path),
})))

const noMatchedRows = computed(() => noMatchedDirs.value.map((path, i) => ({
  index: i + 1,
  path: String(path),
})))

function parseLocateInfo(message: string): {
  canLocate: boolean
  panels: string[]
  path: string
} {
  const text = String(message || '')
  if (text.startsWith('W_BACKUP_GATE_FAILED:')) {
    const matched = gateFailedDirs.value.find((p) => text.includes(String(p)))
    return {
      canLocate: true,
      panels: ['gate-failed'],
      path: matched ? String(matched) : '',
    }
  }
  if (text.startsWith('W_APPLY_DIR_NO_MATCHED_ENTRIES:')) {
    const prefix = 'W_APPLY_DIR_NO_MATCHED_ENTRIES:'
    const path = text.slice(prefix.length).trim()
    return {
      canLocate: true,
      panels: ['no-matched'],
      path,
    }
  }
  if (text.startsWith('W_APPLY_NO_EFFECT:')) {
    return {
      canLocate: true,
      panels: ['gate-failed', 'no-matched'],
      path: '',
    }
  }
  return {
    canLocate: false,
    panels: [],
    path: '',
  }
}

const operationWarningRows = computed(() => operationWarnings.value.map((w, i) => {
  const info = parseLocateInfo(w)
  return {
    index: i + 1,
    message: w,
    canLocate: info.canLocate,
    panels: info.panels,
    path: info.path,
  }
}))

const operationErrorRows = computed(() => operationErrors.value.map((e, i) => {
  const text = String(e || '')
  const code = text.split(':', 1)[0] || 'UNKNOWN'
  let path = ''
  if (code === 'E_COPY_FAILED' || code === 'E_DELETE_FAILED') {
    const parts = text.split(': ')
    path = parts.length >= 2 ? parts[1] : ''
  } else if (code === 'E_SOURCE_NOT_FOUND') {
    const prefix = 'E_SOURCE_NOT_FOUND: '
    path = text.startsWith(prefix) ? text.slice(prefix.length).trim() : ''
  }
  return {
    index: i + 1,
    code,
    path,
    message: text,
  }
}))

const operationErrorGroups = computed(() => {
  const counter = new Map<string, number>()
  for (const row of operationErrorRows.value) {
    counter.set(row.code, (counter.get(row.code) || 0) + 1)
  }
  return Array.from(counter.entries())
    .map(([code, count]) => ({ code, count }))
    .sort((a, b) => b.count - a.count)
})

const filteredOperationErrorRows = computed(() => {
  if (!selectedErrorCode.value) {
    return operationErrorRows.value
  }
  return operationErrorRows.value.filter((row) => row.code === selectedErrorCode.value)
})

const diagnosticsHint = computed(() => {
  const g = gateFailedDirs.value.length
  const n = noMatchedDirs.value.length
  return `${STR.operationsPage.diagHintPrefix} gate=${g}，no-match=${n}`
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

function formatSize(bytes: number): string {
  if (!bytes || bytes === 0) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

function formatMtime(mtime: number): string {
  if (!mtime || mtime === 0) return '-'
  return new Date(mtime * 1000).toLocaleString()
}

function copyDiagPath(path: string) {
  const text = path.trim()
  if (!text) {
    ElMessage.warning(STR.operationsPage.copyPathEmpty)
    return
  }

  if (typeof navigator === 'undefined' || !navigator.clipboard) {
    ElMessage.warning(STR.operationsPage.copyPathUnsupported)
    return
  }

  navigator.clipboard.writeText(text)
    .then(() => {
      ElMessage.success(STR.operationsPage.copyPathSuccess)
    })
    .catch(() => {
      ElMessage.error(STR.operationsPage.copyPathFailed)
    })
}

function diagRowClassName({ row }: { row: Record<string, unknown> }) {
  return String(row.path || '') === diagFocusedPath.value ? 'diag-row-focused' : ''
}

function locateWarning(row: {
  canLocate: boolean
  panels: string[]
  path: string
}) {
  if (!row.canLocate) {
    return
  }
  if (!applyDiagnostics.value) {
    ElMessage.warning(STR.operationsPage.locateNoDiagnostics)
    return
  }

  diagExpandedPanels.value = row.panels
  diagFocusedPath.value = row.path || ''
  showOpWarningsDialog.value = false

  nextTick(() => {
    const card = document.getElementById('apply-diagnostics-card')
    if (card) {
      card.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  })
}

function quickLocateFromSummary() {
  const firstLocatable = operationWarningRows.value.find((row) => row.canLocate)
  if (firstLocatable) {
    locateWarning(firstLocatable)
    return
  }
  showOpWarningsDialog.value = true
}

function quickLocateErrorFromSummary() {
  const topGroup = operationErrorGroups.value[0]
  selectedErrorCode.value = topGroup ? topGroup.code : ''
  showOpErrorsDialog.value = true
}

function hasErrorPath(row: { path?: string }) {
  return Boolean(String(row.path || '').trim())
}

function populateResults(data: Record<string, unknown>) {
  const trees = Array.isArray(data.trees) ? data.trees : []
  const mapping = Array.isArray(data.final_mapping) ? data.final_mapping : []
  const warnings = Array.isArray(data.warnings) ? data.warnings : []
  const errors = Array.isArray(data.errors) ? data.errors : []

  localResults.value = {
    trees_count: trees.length,
    mapping_count: mapping.length,
    warnings: warnings as string[],
    errors: errors as string[],
    stats: {},
    _rawMapping: mapping as any, // for mappingStats computed
  } as any

  // Also populate forest store for consistency
  if (trees.length > 0) store.trees = trees as any[]
  if (mapping.length > 0) store.finalMapping = mapping as any[]
}

/** Load mapping results from workspace, falling back to forest store */
async function loadMappingFromWorkspace() {
  const wid = workspaceId.value
  if (!wid) {
    loadState.value = 'error'
    loadError.value = '未找到工作区 ID，请从工作区列表进入'
    return
  }

  loadState.value = 'loading'

  // 1. Try workspace API
  try {
    const resp = await apiGet<Record<string, unknown>>(`/workspace/${wid}/forest/mapping`)
    if (resp.ok && resp.data) {
      populateResults(resp.data)
      loadState.value = 'loaded'
      return
    }
    // API returned ok:false — likely "mapping not yet computed"
    // fall through to forest store
  } catch {
    // network error — fall through to forest store
  }

  // 2. Fallback to forest store in-memory data
  if (store.trees.length > 0 || store.finalMapping.length > 0) {
    localResults.value = {
      trees_count: store.trees.length,
      mapping_count: store.finalMapping.length,
      warnings: store.warnings,
      errors: store.errors,
      stats: store.stats,
    }
  }

  loadState.value = 'loaded'
}

// ── lifecycle ──────────────────────────────────────────────────────────

onMounted(async () => {
  if (workspaceId.value) {
    appStore.setCurrentWorkspaceId(workspaceId.value)
  }
  await loadMappingFromWorkspace()
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
  dryRunEntries.value = []
  dryRunOperation.value = ''
  applyDiagnostics.value = null
  diagExpandedPanels.value = []
  diagFocusedPath.value = ''
  progress.value = { step: 'backup', finished: 0, total: -1, message: '准备中...' }

  await streamSse(`/workspace/${workspaceId.value}/pipeline/backup`, {
    dry_run: dryRun.value,
  }, {
    onProgress(p: SseProgress) {
      progress.value = p
    },
    onResult(data: unknown) {
      const result = data as Record<string, any>
      const backedUp = result?.data?.backed_up || []
      const skipped = result?.data?.backup_skipped || []
      const errs: string[] = result?.data?.backup_errors || result?.errors || []
      const warns: string[] = result?.warnings || []
      const isDry = result?.data?.dry_run
      operationWarnings.value = warns
      operationErrors.value = errs
      selectedErrorCode.value = ''
      if (backedUp.length > 0) {
        dryRunEntries.value = backedUp
        dryRunOperation.value = 'backup'
      }
      const prefix = isDry ? '[dry-run] ' : ''
      if (errs.length > 0) {
        ElMessage.warning(`${prefix}备份完成：${backedUp.length} 个文件备份，${skipped.length} 个跳过，${errs.length} 个错误`)
      } else {
        ElMessage.success(`${prefix}备份完成：${backedUp.length} 个文件备份，${skipped.length} 个跳过`)
      }
      operating.value = null
    },
    onError(msg: string) {
      operationErrors.value = [msg]
      ElMessage.error(`${STR.operationsPage.operationFailed}: ${msg}`)
      operating.value = null
    },
  })
}

/** 应用映射 */
async function doApply() {
  operating.value = 'apply'
  dryRunEntries.value = []
  dryRunOperation.value = ''
  progress.value = { step: 'apply', finished: 0, total: -1, message: '准备中...' }

  await streamSse(`/workspace/${workspaceId.value}/pipeline/apply`, {
    dry_run: dryRun.value,
  }, {
    onProgress(p: SseProgress) {
      progress.value = p
    },
    onResult(data: unknown) {
      const result = data as Record<string, any>
      const applied = result?.data?.applied || []
      const skipped = result?.data?.apply_skipped || []
      const errs: string[] = result?.data?.apply_errors || result?.errors || []
      const warns: string[] = result?.warnings || []
      const diagnostics = (result?.data?.apply_diagnostics || {}) as Record<string, unknown>
      applyDiagnostics.value = Object.keys(diagnostics).length > 0 ? diagnostics : null
      diagExpandedPanels.value = []
      diagFocusedPath.value = ''
      const gateFailed = Array.isArray(diagnostics?.gate_failed_dirs)
        ? diagnostics.gate_failed_dirs.length
        : 0
      const noMatched = Array.isArray(diagnostics?.no_matched_entry_dirs)
        ? diagnostics.no_matched_entry_dirs.length
        : 0
      const isDry = result?.data?.dry_run
      operationWarnings.value = warns
      operationErrors.value = errs
      selectedErrorCode.value = ''
      if (applied.length > 0) {
        dryRunEntries.value = applied
        dryRunOperation.value = 'apply'
      }
      const prefix = isDry ? '[dry-run] ' : ''
      const noOp = !isDry && applied.length === 0 && skipped.length === 0
      const diagText = (gateFailed > 0 || noMatched > 0)
        ? `，gate失败目录 ${gateFailed}，无匹配目录 ${noMatched}`
        : ''
      if (errs.length > 0 || warns.length > 0 || noOp) {
        ElMessage.warning(
          `${prefix}应用完成：${applied.length} 个操作，${skipped.length} 个跳过，${errs.length} 个错误，${warns.length} 个警告${diagText}`,
        )
      } else {
        ElMessage.success(`${prefix}应用完成：${applied.length} 个操作，${skipped.length} 个跳过`)
      }
      operating.value = null
    },
    onError(msg: string) {
      operationErrors.value = [msg]
      ElMessage.error(`${STR.operationsPage.operationFailed}: ${msg}`)
      operating.value = null
    },
  })
}

/** 恢复备份 */
async function doRestore() {
  operating.value = 'restore'
  dryRunEntries.value = []
  dryRunOperation.value = ''
  applyDiagnostics.value = null
  diagExpandedPanels.value = []
  diagFocusedPath.value = ''
  progress.value = { step: 'restore', finished: 0, total: -1, message: '准备中...' }

  await streamSse(`/workspace/${workspaceId.value}/pipeline/restore`, {
    force: false,
  }, {
    onProgress(p: SseProgress) {
      progress.value = p
    },
    onResult(data: unknown) {
      const result = data as Record<string, any>
      const restored = result?.data?.restored || []
      const skipped = result?.data?.skipped || []
      const errs: string[] = result?.errors || result?.data?.restore_errors || []
      const warns: string[] = result?.warnings || []
      operationWarnings.value = warns
      operationErrors.value = errs
      selectedErrorCode.value = ''
      if (restored.length > 0) {
        dryRunEntries.value = restored
        dryRunOperation.value = 'restore'
      }
      if (errs.length > 0) {
        ElMessage.warning(`恢复完成：${restored.length} 个文件恢复，${skipped.length} 个跳过，${errs.length} 个错误`)
      } else {
        ElMessage.success(`恢复完成：${restored.length} 个文件恢复，${skipped.length} 个跳过`)
      }
      operating.value = null
    },
    onError(msg: string) {
      operationErrors.value = [msg]
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

/* 映射摘要表格：统一标签列宽度，外表格固定布局让四列均分 */
.summary-table :deep(table) {
  table-layout: fixed;
  width: 100%;
}
.summary-table :deep(.el-descriptions__label) {
  width: 80px;
  min-width: 80px;
  text-align: right;
}
.summary-table :deep(.el-descriptions__content) {
  text-align: center;
}

:deep(.diag-row-focused td) {
  background-color: #fff7e6 !important;
}
</style>

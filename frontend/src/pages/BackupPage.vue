<template>
  <div>
    <h2>{{ STR.backupPage.title }}</h2>
    <el-card shadow="never" style="margin-bottom: 16px;">
      <el-form :model="form" label-width="120px">
        <el-form-item :label="STR.backupPage.backupDirLabel">
          <el-input v-model="form.backupDir" :placeholder="STR.backupPage.backupDirPlaceholder" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="isScanning" @click="onScan">{{ STR.backupPage.scanBtn }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table
      v-if="backupDirs.length > 0"
      :data="backupDirs"
      @row-click="onInspect"
      highlight-current-row
    >
      <el-table-column prop="name" :label="STR.backupPage.name" width="200" />
      <el-table-column :label="STR.backupPage.path">
        <template #default="{ row }">
          {{ ensureTrailingSlash(row.path) }}
        </template>
      </el-table-column>
      <el-table-column prop="file_count" :label="STR.backupPage.fileCount" width="80" />
      <el-table-column :label="STR.backupPage.createdAt" width="160">
        <template #default="{ row }">
          {{ row.created_at ? new Date(row.created_at * 1000).toLocaleString() : '-' }}
        </template>
      </el-table-column>
      <el-table-column :label="STR.backupPage.actions" width="100">
        <template #default="{ row }">
          <el-button
            size="small"
            type="danger"
            :disabled="isRestoring"
            @click.stop="confirmRestore(row)"
          >
            {{ STR.backupPage.restore }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-else-if="!isScanning" :description="STR.backupPage.emptyDescription" />

    <!-- Inspection detail panel -->
    <el-card v-if="inspectResult" shadow="never" style="margin-top: 16px;">
      <template #header>
        <span>{{ STR.backupPage.detailTitle }}{{ ensureTrailingSlash(inspectResult.path) }}</span>
      </template>
      <div>
        <p><strong>{{ STR.backupPage.fileCount }}：</strong>{{ inspectResult.file_count }}</p>
        <p><strong>{{ STR.backupPage.dirtyStatus }}：</strong>
          <el-tag :type="inspectResult.dirty?.dirty ? 'danger' : 'success'" size="small">
            {{ inspectResult.dirty?.dirty ? STR.backupPage.dirty : STR.backupPage.clean }}
          </el-tag>
        </p>
        <p v-if="inspectResult.dirty?.errors?.length">
          <strong>{{ STR.backupPage.dirtyErrors }}</strong>
          <el-tag v-for="(e, i) in inspectResult.dirty.errors" :key="i" type="danger" size="small" style="margin-right: 4px;">{{ e }}</el-tag>
        </p>
        <p><strong>{{ STR.backupPage.conflictStatus }}：</strong>
          <el-tag :type="inspectResult.conflicts?.clean ? 'success' : 'warning'" size="small">
            {{ inspectResult.conflicts?.clean ? STR.backupPage.noConflict : STR.backupPage.hasConflict }}
          </el-tag>
        </p>
        <p v-if="inspectResult.conflicts?.conflicts?.length">
          <strong>{{ STR.backupPage.conflictList }}</strong>
        </p>
        <ul v-if="inspectResult.conflicts?.conflicts?.length">
          <li v-for="(c, i) in inspectResult.conflicts.conflicts" :key="i">{{ c }}</li>
        </ul>
        <p><strong>{{ STR.backupPage.fileList }}</strong></p>
        <el-table
          v-if="inspectResult.files?.length"
          :data="inspectResult.files"
          size="small"
          max-height="300"
          @selection-change="onFileSelectionChange"
        >
          <el-table-column type="selection" width="40" />
          <el-table-column prop="relpath" :label="STR.backupPage.relpath" />
          <el-table-column prop="size" :label="STR.backupPage.size" width="80">
            <template #default="{ row }">
              <span style="font-size: 12px;">{{ formatSize(row.size) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="hash" :label="STR.backupPage.sha256" width="80">
            <template #default="{ row }">
              <span style="font-family: monospace; font-size: 11px;">{{ row?.hash?.slice(0, 12) || '-' }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else :description="STR.backupPage.noFiles" />
      </div>
    </el-card>

    <!-- Restore confirmation dialog -->
    <el-dialog v-model="restoreDialogVisible" :title="STR.backupPage.restoreTitle" width="480px">
      <p>{{ STR.backupPage.restoreConfirm }}</p>
      <p style="font-weight: bold; word-break: break-all;">{{ ensureTrailingSlash(restoreTargetPath) }}</p>
      <p v-if="selectedFiles.length > 0" style="font-size: 12px; color: #409eff;">
        {{ STR.backupPage.selectedFiles(selectedFiles.length) }}
      </p>
      <p v-else style="font-size: 12px; color: #999;">
        {{ STR.backupPage.noFilesSelected }}
      </p>
      <p style="font-size: 12px; color: #999; margin-top: 4px;">{{ STR.backupPage.overwriteWarning }}</p>
      <template #footer>
        <el-button @click="restoreDialogVisible = false">{{ STR.backupPage.cancel }}</el-button>
        <el-button type="danger" :loading="isRestoring" @click="doRestore">{{ STR.backupPage.confirmRestore }}</el-button>
      </template>
    </el-dialog>

    <!-- Restore progress -->
    <el-card v-if="restoreProgress.step" shadow="never" style="margin-top: 16px;">
      <template #header><span>{{ STR.backupPage.restoreProgress }}</span></template>
      <div>
        <p>{{ STR.backupPage.step }}：{{ restoreProgress.step }}</p>
        <p>{{ STR.backupPage.progress }}：{{ restoreProgress.finished }} / {{ restoreProgress.total }}</p>
        <p v-if="restoreProgress.message">{{ restoreProgress.message }}</p>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { apiPost } from '../api/client'
import { streamSse } from '../api/sse'
import type { SseProgress } from '../api/sse'
import { ensureTrailingSlash } from '../utils/paths'
import { STR } from '../locales/zh-CN'

interface BackupDir {
  name: string
  path: string
  file_count: number
  created_at?: number
}

interface BackupFile {
  relpath: string
  hash: string
  size?: number
}

interface InspectResult {
  path: string
  file_count: number
  files: BackupFile[]
  dirty: {
    dirty: boolean
    errors: string[]
    partial_files: string[]
  }
  conflicts: {
    clean: boolean
    conflicts: string[]
  }
}

const form = reactive({
  backupDir: '',
})

const backupDirs = ref<BackupDir[]>([])
const isScanning = ref(false)
const isRestoring = ref(false)

// Inspection
const inspectResult = ref<InspectResult | null>(null)

// File selection (for partial restore)
const selectedFiles = ref<string[]>([])

function onFileSelectionChange(selection: BackupFile[]) {
  selectedFiles.value = selection.map(f => f.relpath)
}

function formatSize(bytes: number | undefined): string {
  if (bytes === undefined || bytes === null) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Restore dialog
const restoreDialogVisible = ref(false)
const restoreTargetPath = ref('')
const restoreProgress = ref<SseProgress>({ step: '', finished: 0, total: -1, message: '' })

async function onScan() {
  if (!form.backupDir.trim()) return
  isScanning.value = true
  inspectResult.value = null
  backupDirs.value = []

  const resp = await apiPost('/backups/list', { dir: form.backupDir.trim() })
  if (resp.ok && resp.data) {
    backupDirs.value = (resp.data as { backups: BackupDir[] }).backups || []
    if (backupDirs.value.length === 0) {
      ElMessage.info(STR.backupPage.noBackups)
    }
  } else {
    const errMsg = resp.errors?.join('; ') || STR.backupPage.scanFailed
    ElMessage.error(errMsg)
  }

  isScanning.value = false
}

async function onInspect(row: BackupDir) {
  const resp = await apiPost('/backups/inspect', { path: row.path })
  if (resp.ok && resp.data) {
    inspectResult.value = resp.data as InspectResult
    selectedFiles.value = [] // reset file selection on new inspect
  } else {
    const errMsg = resp.errors?.join('; ') || STR.backupPage.inspectFailed
    ElMessage.error(errMsg)
    inspectResult.value = null
  }
}

function confirmRestore(row: BackupDir) {
  restoreTargetPath.value = row.path
  restoreDialogVisible.value = true
}

async function doRestore() {
  restoreDialogVisible.value = false
  isRestoring.value = true
  restoreProgress.value = { step: STR.backupPage.restoreStepStarted, finished: 0, total: -1, message: '' }

  const backupPath = restoreTargetPath.value
  const targetFiles = selectedFiles.value.length > 0 ? selectedFiles.value : null

  await streamSse('/pipeline/restore', {
    backup_dir: backupPath,
    target_files: targetFiles,
  }, {
    onProgress(p: SseProgress) {
      restoreProgress.value = p
    },
    onResult(data: unknown) {
      const resp = data as { ok?: boolean; data?: { restored?: string[]; errors?: string[] } } | null
      const restored = resp?.data?.restored || []
      const errors = resp?.data?.errors || []
      const summary = STR.backupPage.restoreComplete(restored.length, errors.length)
      restoreProgress.value = { step: STR.backupPage.restoreStepCompleted, finished: 1, total: 1, message: summary }
      ElMessage.success(summary)
      isRestoring.value = false
    },
    onError(msg: string) {
      restoreProgress.value = { step: STR.backupPage.restoreStepError, finished: 0, total: -1, message: msg }
      ElMessage.error(STR.backupPage.restoreFailed(msg))
      isRestoring.value = false
    },
  })

  isRestoring.value = false
}
</script>

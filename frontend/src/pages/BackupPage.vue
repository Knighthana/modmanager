<template>
  <div>
    <h2>备份管理</h2>
    <el-card shadow="never" style="margin-bottom: 16px;">
      <el-form :model="form" label-width="120px">
        <el-form-item label="备份目录">
          <el-input v-model="form.backupDir" placeholder="输入备份目录路径" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="isScanning" @click="onScan">扫描备份</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-table
      v-if="backupDirs.length > 0"
      :data="backupDirs"
      @row-click="onInspect"
      highlight-current-row
    >
      <el-table-column prop="name" label="名称" width="200" />
      <el-table-column prop="path" label="路径" />
      <el-table-column prop="file_count" label="文件数" width="80" />
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button
            size="small"
            type="danger"
            :disabled="isRestoring"
            @click.stop="confirmRestore(row)"
          >
            恢复
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-else-if="!isScanning" description="尚未扫描备份目录" />

    <!-- Inspection detail panel -->
    <el-card v-if="inspectResult" shadow="never" style="margin-top: 16px;">
      <template #header>
        <span>备份详情：{{ inspectResult.path }}</span>
      </template>
      <div>
        <p><strong>文件数：</strong>{{ inspectResult.file_count }}</p>
        <p><strong>脏状态：</strong>
          <el-tag :type="inspectResult.dirty?.dirty ? 'danger' : 'success'" size="small">
            {{ inspectResult.dirty?.dirty ? '脏' : '干净' }}
          </el-tag>
        </p>
        <p v-if="inspectResult.dirty?.errors?.length">
          <strong>脏状态错误：</strong>
          <el-tag v-for="(e, i) in inspectResult.dirty.errors" :key="i" type="danger" size="small" style="margin-right: 4px;">{{ e }}</el-tag>
        </p>
        <p><strong>冲突状态：</strong>
          <el-tag :type="inspectResult.conflicts?.clean ? 'success' : 'warning'" size="small">
            {{ inspectResult.conflicts?.clean ? '无冲突' : '有冲突' }}
          </el-tag>
        </p>
        <p v-if="inspectResult.conflicts?.conflicts?.length">
          <strong>冲突列表：</strong>
        </p>
        <ul v-if="inspectResult.conflicts?.conflicts?.length">
          <li v-for="(c, i) in inspectResult.conflicts.conflicts" :key="i">{{ c }}</li>
        </ul>
        <p><strong>文件列表：</strong></p>
        <el-table v-if="inspectResult.files?.length" :data="inspectResult.files" size="small" max-height="300">
          <el-table-column prop="relpath" label="相对路径" />
          <el-table-column prop="hash" label="SHA256" width="80">
            <template #default="{ row }">
              <span style="font-family: monospace; font-size: 11px;">{{ row?.hash?.slice(0, 12) || '-' }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="无文件记录" />
      </div>
    </el-card>

    <!-- Restore confirmation dialog -->
    <el-dialog v-model="restoreDialogVisible" title="确认恢复" width="400px">
      <p>确定要从以下备份目录恢复文件？</p>
      <p style="font-weight: bold; word-break: break-all;">{{ restoreTargetPath }}</p>
      <p style="font-size: 12px; color: #999;">此操作将覆盖目标位置的现有文件。</p>
      <template #footer>
        <el-button @click="restoreDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="isRestoring" @click="doRestore">确认恢复</el-button>
      </template>
    </el-dialog>

    <!-- Restore progress -->
    <el-card v-if="restoreProgress.step" shadow="never" style="margin-top: 16px;">
      <template #header><span>恢复进度</span></template>
      <div>
        <p>步骤：{{ restoreProgress.step }}</p>
        <p>进度：{{ restoreProgress.finished }} / {{ restoreProgress.total }}</p>
        <p v-if="restoreProgress.message">{{ restoreProgress.message }}</p>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { apiPost } from '../api/client'
import { streamSse } from '../api/sse'
import type { SseProgress } from '../api/sse'

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

// Restore dialog
const restoreDialogVisible = ref(false)
const restoreTargetPath = ref('')
const restoreProgress = ref<SseProgress>({ step: '', finished: 0, total: -1, message: '' })

async function onScan() {
  if (!form.backupDir.trim()) return
  isScanning.value = true
  inspectResult.value = null

  const resp = await apiPost('/backups/list', { dir: form.backupDir.trim() })
  if (resp.ok && resp.data) {
    backupDirs.value = (resp.data as { backups: BackupDir[] }).backups || []
  } else {
    backupDirs.value = []
  }

  isScanning.value = false
}

async function onInspect(row: BackupDir) {
  const resp = await apiPost('/backups/inspect', { path: row.path })
  if (resp.ok && resp.data) {
    inspectResult.value = resp.data as InspectResult
  }
}

function confirmRestore(row: BackupDir) {
  restoreTargetPath.value = row.path
  restoreDialogVisible.value = true
}

async function doRestore() {
  restoreDialogVisible.value = false
  isRestoring.value = true
  restoreProgress.value = { step: '开始', finished: 0, total: -1, message: '' }

  const backupPath = restoreTargetPath.value

  await streamSse('/pipeline/restore', {
    backup_dir: backupPath,
    target_files: null,
  }, {
    onProgress(p: SseProgress) {
      restoreProgress.value = p
    },
    onResult(_data: unknown) {
      restoreProgress.value = { step: '完成', finished: 1, total: 1, message: '恢复完成' }
      isRestoring.value = false
    },
    onError(msg: string) {
      restoreProgress.value = { step: '错误', finished: 0, total: -1, message: msg }
      isRestoring.value = false
    },
  })

  isRestoring.value = false
}
</script>

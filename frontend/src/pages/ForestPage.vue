<template>
  <div>
    <h2>Forest 可视化</h2>

    <!-- PipelineForm -->
    <el-card shadow="never" style="margin-bottom: 16px;">
      <el-form :model="form" label-width="120px">
        <el-form-item label="Database path">
          <el-input v-model="form.database" placeholder="/path/to/database.json" />
        </el-form-item>
        <el-form-item label="Rules paths">
          <el-input v-model="form.rulesPaths" placeholder="Comma-separated paths to kmm_rule files" />
        </el-form-item>
        <el-form-item label="Backup dir">
          <el-input v-model="form.backupDir" placeholder="/path/to/backup" />
        </el-form-item>
        <el-form-item label="Dry run">
          <el-switch v-model="form.dryRun" />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="store.isRunning"
            :disabled="store.isRunning"
            @click="onRun"
          >
            {{ store.isRunning ? '运行中...' : '▶ 运行' }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- ResultSummary -->
    <el-row v-if="hasResult" :gutter="16" style="margin-bottom: 16px;">
      <el-col :span="6">
        <el-card shadow="never">
          <span style="font-size: 13px; color: var(--el-text-color-secondary);">Forest 节点</span>
          <div style="font-size: 24px; font-weight: 600;">{{ store.forest.length }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <span style="font-size: 13px; color: var(--el-text-color-secondary);">冲突</span>
          <div style="font-size: 24px; font-weight: 600;">{{ store.conflictList.length }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <span style="font-size: 13px; color: var(--el-text-color-secondary);">最终映射</span>
          <div style="font-size: 24px; font-weight: 600;">{{ store.finalMapping.length }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <span style="font-size: 13px; color: var(--el-text-color-secondary);">错误</span>
          <div style="font-size: 24px; font-weight: 600; color: var(--el-color-danger);">{{ store.errors.length }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- ForestViewer -->
    <ForestViewer />
  </div>
</template>

<script setup lang="ts">
import { reactive, computed } from 'vue'
import { useForestStore } from '../stores/forest'
import ForestViewer from '../components/ForestViewer.vue'

const store = useForestStore()

const form = reactive({
  database: '',
  rulesPaths: '',
  backupDir: '',
  dryRun: true,
})

const hasResult = computed(() => store.forest.length > 0 || store.errors.length > 0)

async function onRun() {
  const rules = form.rulesPaths
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)

  // For minimal testing, use a sensible default if empty
  if (!form.database) {
    form.database = '{}'
  }

  let database: Record<string, unknown>
  try {
    database = JSON.parse(form.database)
  } catch {
    database = {}
  }

  await store.runPipeline({
    database,
    kmm_rule_paths: rules,
    user_config_path: '',
    backup_dir: form.backupDir,
    dry_run: form.dryRun,
  })
}
</script>

<template>
  <div>
    <h2>Forest 可视化</h2>

    <!-- 数据源发现面板 -->
    <el-card shadow="never" style="margin-bottom: 16px;">
      <template #header>
        <span>数据源发现</span>
      </template>
      <el-form :model="form" label-width="140px">
        <el-form-item label="Working pathstyle">
          <el-select v-model="form.workingPathstyle" style="width: 200px;">
            <el-option label="auto" value="auto" />
            <el-option label="linux" value="linux" />
            <el-option label="windows" value="windows" />
          </el-select>
        </el-form-item>
        <el-form-item label="Greedy parsing">
          <el-switch v-model="form.greedyParsing" />
        </el-form-item>
        <el-form-item label="Cache path">
          <el-input v-model="form.cachePath" placeholder="/tmp/modmanager_database_generated.json" />
        </el-form-item>
        <el-form-item>
          <el-button
            type="warning"
            :loading="store.isRunning"
            :disabled="store.isRunning"
            @click="onDiscover"
          >
            {{ store.isRunning ? '探测中...' : '🔍 自动探测 Steam 库' }}
          </el-button>
        </el-form-item>
        <!-- 探测结果摘要 -->
        <el-form-item v-if="store.databaseSummary && !store.errors.length" label="探测结果">
          <el-tag type="success" style="margin-right: 8px;">
            发现 {{ store.databaseSummary.libraries }} 个库
          </el-tag>
          <el-tag type="success" style="margin-right: 8px;">
            {{ store.databaseSummary.games }} 个游戏
          </el-tag>
          <el-tag type="success">
            {{ store.databaseSummary.mods }} 个 mod
          </el-tag>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- PipelineForm -->
    <el-card shadow="never" style="margin-bottom: 16px;">
      <template #header>
        <span>Pipeline 参数</span>
      </template>
      <el-form :model="form" label-width="140px">
        <el-form-item label="Database 路径">
          <el-input v-model="form.databasePath" placeholder="自动探测后自动填入">
            <template #append>
              <el-button @click="form.databasePath = ''; form.databaseJson = ''">清除</el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="Database JSON (手动)">
          <el-input
            v-model="form.databaseJson"
            type="textarea"
            :rows="3"
            placeholder='{"steamlib": [...], ...}'
            :disabled="!!form.databasePath"
          />
        </el-form-item>
        <el-form-item label="Rules paths">
          <el-input v-model="form.rulesPaths" placeholder="Comma-separated paths to kmm_rule files" />
        </el-form-item>
        <el-form-item label="User config 路径">
          <el-input v-model="form.userConfigPath" placeholder="自动探测后自动填入" />
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

const hasResult = computed(() => store.forest.length > 0 || store.errors.length > 0)

async function onDiscover() {
  await store.discoverDatabase({
    mode: 'auto',
    paths: null,
    workingPathstyle: form.workingPathstyle,
    greedyParsing: form.greedyParsing,
    cachePath: form.cachePath,
  })

  // Auto-populate form on success
  if (store.databaseSummary && !store.errors.length) {
    form.databasePath = form.cachePath
    form.userConfigPath = '/tmp/modmanager_userconfig_generated.json'
  }
}

async function onRun() {
  const rules = form.rulesPaths
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)

  let database: Record<string, unknown>
  if (form.databasePath && store.storedDatabase) {
    database = store.storedDatabase
  } else if (form.databaseJson) {
    try {
      database = JSON.parse(form.databaseJson)
    } catch {
      database = {}
    }
  } else {
    database = {}
  }

  await store.runPipeline({
    database,
    kmm_rule_paths: rules,
    user_config_path: form.userConfigPath || '',
    backup_dir: form.backupDir,
    dry_run: form.dryRun,
  })
}
</script>

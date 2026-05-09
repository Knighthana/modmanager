<template>
  <div>
    <h2>{{ STR.forestPage.title }}</h2>

    <!-- PipelineForm -->
    <el-card shadow="never" style="margin-bottom: 16px;">
      <template #header>
        <span>{{ STR.forestPage.pipelineParams }}</span>
      </template>
      <el-form :model="store.pipelineForm" label-width="140px">
        <el-form-item :label="STR.forestPage.dbJsonLabel">
          <el-input
            v-model="store.pipelineForm.databaseJson"
            type="textarea"
            :rows="7"
            :placeholder="STR.forestPage.dbJsonPlaceholder()"
          />
        </el-form-item>
        <el-form-item :label="STR.forestPage.rulesPathsLabel">
          <el-input v-model="store.pipelineForm.rulesPaths" :placeholder="STR.forestPage.rulesPathsPlaceholder" />
        </el-form-item>
        <el-form-item :label="STR.forestPage.userConfigLabel">
          <el-input v-model="store.pipelineForm.userConfigPath" :placeholder="STR.forestPage.userConfigPlaceholder" />
        </el-form-item>
        <el-form-item :label="STR.forestPage.backupDirLabel">
          <el-input v-model="store.pipelineForm.backupDir" :placeholder="STR.forestPage.backupDirPlaceholder" />
        </el-form-item>
        <el-form-item :label="STR.forestPage.dryRunLabel">
          <el-switch v-model="store.pipelineForm.dryRun" />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="store.isRunning"
            :disabled="store.isRunning"
            @click="onCompute"
          >
            {{ store.isRunning ? STR.forestPage.computeBtnRunning : STR.forestPage.computeBtn }}
          </el-button>
          <el-button
            type="success"
            :loading="store.isRunning"
            :disabled="store.isRunning"
            @click="onRun"
            style="margin-left: 8px;"
          >
            {{ STR.forestPage.runBtn }}
          </el-button>
          <span style="margin-left: 8px; font-size: 12px; color: #999;">
            {{ STR.forestPage.hintText }}
          </span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- ResultSummary -->
    <el-row v-if="hasResult" :gutter="16" style="margin-bottom: 16px;">
      <el-col :span="6">
        <el-card shadow="never">
          <span style="font-size: 13px; color: var(--el-text-color-secondary);">{{ STR.forestPage.treesCount }}</span>
          <div style="font-size: 24px; font-weight: 600;">{{ store.trees.length }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <span style="font-size: 13px; color: var(--el-text-color-secondary);">{{ STR.forestPage.conflicts }}</span>
          <div style="font-size: 24px; font-weight: 600;">{{ store.conflictList.length }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <span style="font-size: 13px; color: var(--el-text-color-secondary);">{{ STR.forestPage.finalMapping }}</span>
          <div style="font-size: 24px; font-weight: 600;">{{ store.finalMapping.length }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <span style="font-size: 13px; color: var(--el-text-color-secondary);">{{ STR.forestPage.errors }}</span>
          <div style="font-size: 24px; font-weight: 600;"
               :style="{ color: store.errors.length > 0 ? 'var(--el-color-danger)' : 'var(--el-text-color-primary)' }">
            {{ store.errors.length }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 错误与警告面板 -->
    <div v-if="store.errors.length || store.warnings.length" style="margin-bottom: 16px;">
      <el-collapse v-model="activeCollapseNames">
        <el-collapse-item v-if="store.errors.length" :title="`${STR.forestPage.errors} (${store.errors.length})`" name="errors">
          <el-alert
            v-for="(err, i) in store.errors"
            :key="'err-' + i"
            :title="err"
            type="error"
            :closable="false"
            style="margin-bottom: 4px; cursor: pointer;"
            @click="(e: MouseEvent) => onMessageClick(err, e)"
          />
        </el-collapse-item>
        <el-collapse-item v-if="store.warnings.length" :title="`${STR.forestPage.warnings} (${store.warnings.length})`" name="warnings">
          <el-alert
            v-for="(warn, i) in store.warnings"
            :key="'warn-' + i"
            :title="warn"
            type="warning"
            :closable="false"
            style="margin-bottom: 4px; cursor: pointer;"
            @click="(e: MouseEvent) => onMessageClick(warn, e)"
          />
        </el-collapse-item>
      </el-collapse>

      <!-- 提示：若全是 W_LOCAL_MOD_MISSING，建议先运行自动探测 -->
      <el-alert
        v-if="store.errors.every(e => e.startsWith('W_')) && store.errors.length > 0"
        :title="STR.forestPage.allWarningsHintTitle"
        :description="STR.forestPage.allWarningsHintDesc"
        type="info"
        :closable="false"
        style="margin-top: 8px;"
      />
    </div>

    <!-- 展示模式切换 -->
    <el-card v-if="hasResult" shadow="never" style="margin-bottom: 16px;">
      <el-form label-width="140px">
        <el-form-item :label="STR.forestPage.displayMode">
          <el-switch
            v-model="showBranchingOnly"
            :active-text="STR.forestPage.branchingOnly"
            :inactive-text="STR.forestPage.allTrees"
          />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- ForestViewer -->
    <ForestViewer :empty-message="emptyMessage" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useForestStore, generateBackupDir } from '../stores/forest'
import ForestViewer from '../components/ForestViewer.vue'
import type { TreeNode } from '../types'
import { showPopup } from '../utils/notify'
import { getDescription } from '../utils/errorCodes'
import { STR } from '../locales/zh-CN'

const store = useForestStore()

const hasResult = computed(() => store.trees.length > 0 || store.errors.length > 0)

const activeCollapseNames = computed(() => {
  const names: string[] = []
  if (store.errors.length) names.push('errors')
  if (store.warnings.length) names.push('warnings')
  return names
})

// 展示模式切换：仅显示分枝（pending）树
const showBranchingOnly = ref(false)

function getFilteredTrees(): TreeNode[] {
  if (!showBranchingOnly.value) return store.trees
  return store.trees.filter(t => t.resolved_state === 'pending')
}

const hasBranchingTrees = computed(() => store.trees.some(t => t.resolved_state === 'pending'))

const emptyMessage = computed(() => {
  if (store.trees.length === 0) {
    return STR.forestPage.emptyNoForest
  }
  if (showBranchingOnly.value) {
    return STR.forestPage.emptyNoBranching
  }
  return ''
})

const isDiscoverDisabled = computed(() =>
  store.pipelineForm.discoveryMode === 'manual' && !store.pipelineForm.manualSteamPath
)

async function onDiscover() {
  await store.discoverDatabase()

  // Auto-populate form on success
  if (store.databaseSummary && !store.errors.length) {
    store.pipelineForm.databasePath = store.pipelineForm.cachePath
    store.pipelineForm.backupDir = generateBackupDir()

    // Also discover + save user_config as a separate step
    await store.loadConfig()
    if (store.userConfig) {
      store.pipelineForm.userConfigPath = '/tmp/modmanager_userconfig_generated.json'
    }
  }
}

function prepareParams() {
  const rules = store.pipelineForm.rulesPaths
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)

  let database: any

  // 优先级 1: Database JSON 非空 → 以此为输入
  if (store.pipelineForm.databaseJson.trim()) {
    try {
      database = JSON.parse(store.pipelineForm.databaseJson)
    } catch {
      database = {}
    }
  }
  // 优先级 2: 自动模式 — storedDatabase 存在（来自自动传入或手动加载）
  else if (!store.dbManualOverride && store.storedDatabase) {
    database = store.storedDatabase
  }
  // 优先级 3: 手动模式 — 发路径字符串，后端自行 resolve + load
  else if (store.dbManualOverride && store.pipelineForm.databasePath) {
    database = store.pipelineForm.databasePath
  }
  // 优先级 4: 无可用数据
  else {
    database = {}
  }

  return {
    database,
    kmm_rule_paths: rules,
    user_config_path: store.pipelineForm.userConfigPath || '',
    backup_dir: store.pipelineForm.backupDir || null,
  }
}

function onMessageClick(msg: string, e: MouseEvent) {
    const desc = getDescription(msg)
    if (desc) {
        showPopup(desc, e.currentTarget as HTMLElement, e)
    }
}

async function fetchVisualizationWithFilter() {
  const filtered = getFilteredTrees()
  if (filtered.length === 0) {
    store.svgContent = ''
    return
  }
  await store.fetchVisualization(filtered)
}

async function onCompute() {
  const params = prepareParams()
  await store.computeOnly({
    ...params,
    dry_run: true,
  })

  // 计算完成后，获取可视化
  if (store.trees.length > 0) {
    await fetchVisualizationWithFilter()
  }
}

async function onRun() {
  const params = prepareParams()
  await store.runPipeline({
    ...params,
    dry_run: store.pipelineForm.dryRun,
  })

  // 运行完成后，获取可视化
  if (store.trees.length > 0) {
    await fetchVisualizationWithFilter()
  }
}

// 切换展示模式时自动重新请求可视化
watch(showBranchingOnly, () => {
  if (store.trees.length > 0) {
    fetchVisualizationWithFilter()
  }
})
</script>

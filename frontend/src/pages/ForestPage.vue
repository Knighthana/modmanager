<template>
  <div>
    <div class="forest-top-bar">
      <h2 style="margin: 0;">{{ STR.forestPage.title }}</h2>
      <div class="top-bar-actions">
        <el-button
          type="primary"
          size="small"
          :loading="store.isRunning"
          :disabled="store.isRunning"
          @click="onCompute"
        >
          {{ store.isRunning ? STR.forestPage.computeBtnRunning : STR.forestPage.computeBtn }}
        </el-button>
        <el-button
          type="success"
          size="small"
          :loading="store.isRunning"
          :disabled="store.isRunning"
          @click="onRun"
        >
          {{ STR.forestPage.runBtn }}
        </el-button>
      </div>
    </div>

    <!-- DatabaseSelector -->
    <div style="margin-bottom: 16px;">
      <DatabaseSelector ref="databaseSelectorRef" />
    </div>

    <!-- 上次计算结果恢复提示 -->
    <el-card
      v-if="lastResultSummary && !hasResult"
      shadow="never"
      style="margin-bottom: 16px;"
    >
      <span style="font-size: 13px; color: var(--el-text-color-secondary);">
        上次计算结果：{{ lastResultSummary.treesCount }} 棵树，{{ lastResultSummary.mappingCount }} 个映射
      </span>
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
import { computed, ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useForestStore } from '../stores/forest'
import ForestViewer from '../components/ForestViewer.vue'
import DatabaseSelector from '../components/DatabaseSelector.vue'
import type { TreeNode } from '../types'
import { showPopup } from '../utils/notify'
import { getDescription } from '../utils/errorCodes'
import { loadWorkspace } from '../utils/persistence'
import { STR } from '../locales/zh-CN'

const store = useForestStore()

const databaseSelectorRef = ref<InstanceType<typeof DatabaseSelector> | null>(null)

// Last result summary restored from localStorage
const lastResultSummary = ref<{ treesCount: number; mappingCount: number } | null>(null)

onMounted(() => {
  const ws = loadWorkspace()
  if (ws.lastDatabase) {
    const perDb = ws.perDatabase[ws.lastDatabase]
    if (perDb?.results) {
      lastResultSummary.value = {
        treesCount: perDb.results.trees_count,
        mappingCount: perDb.results.mapping_count,
      }

      // Check result staleness (older than 24 hours)
      const resultTimestamp = perDb.results.timestamp
      if (resultTimestamp) {
        const resultAge = Date.now() - new Date(resultTimestamp).getTime()
        const isStale = resultAge > 24 * 60 * 60 * 1000 // 24 hours

        if (isStale) {
          const hoursOld = Math.floor(resultAge / (60 * 60 * 1000))
          ElMessage.warning(`计算结果已 ${hoursOld} 小时未更新，建议重新计算以确保结果最新`)
        }
      }
    }
  }
})

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

function prepareParams() {
  const rules = store.pipelineForm.rulesPaths
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)

  const selectedDb = databaseSelectorRef.value?.selectedDatabase ?? 'default'

  // Load decisions from workspace
  const ws = loadWorkspace()
  const decisions = ws.perDatabase?.[selectedDb]?.decisions

  return {
    database_name: selectedDb,
    kmm_rule_paths: rules,
    managed_entries: decisions?.managed_entries,
    branch_decisions: decisions?.branch_decisions,
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

<style scoped>
.forest-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.top-bar-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>

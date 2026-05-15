<template>
  <div class="forest-page gui-page">
    <div class="forest-top-bar">
      <div class="forest-controls">
        <el-button size="small" @click="resetView">🔄 重置视图</el-button>
        <el-button size="small" @click="toggleMinimap">📐 小地图</el-button>
        <el-switch
          v-if="hasResult"
          v-model="showBranchingOnly"
          size="small"
          active-text="仅分岔"
          inactive-text="全部"
          style="margin-left:8px;"
        />
      </div>
      <div class="forest-actions">
        <el-button size="small" @click="showDrawer = !showDrawer">📊 摘要</el-button>
      </div>
    </div>

    <!-- 上次计算结果 -->
    <div v-if="lastResultSummary && !hasResult" style="margin-bottom:12px;font-size:13px;color:var(--el-text-color-secondary);">
      上次计算结果：{{ lastResultSummary.treesCount }} 棵树，{{ lastResultSummary.mappingCount }} 个映射。在计算准备页重新计算以查看森林图。
    </div>

    <!-- 错误 / 警告区 -->
    <div v-if="store.errors.length > 0 || store.warnings.length > 0" style="margin-bottom:12px;max-height:120px;overflow-y:auto;">
      <el-alert
        v-for="(msg, i) in [...store.errors, ...store.warnings]"
        :key="i"
        :title="msg"
        :type="store.errors.includes(msg) ? 'error' : 'warning'"
        :closable="false"
        style="margin-bottom:4px;"
      />
    </div>

    <!-- ForestViewer -->
    <ForestViewer ref="forestViewerRef" :empty-message="emptyMessage" />

    <!-- Drawer -->
    <el-drawer v-model="showDrawer" title="摘要" direction="rtl" size="360px">
      <div v-if="store.trees.length > 0" style="padding:0 16px;">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="树">{{ store.trees.length }}</el-descriptions-item>
          <el-descriptions-item label="映射">{{ store.finalMapping.length }}</el-descriptions-item>
          <el-descriptions-item label="警告">{{ store.warnings.length }}</el-descriptions-item>
          <el-descriptions-item label="错误">{{ store.errors.length }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useForestStore } from '../stores/forest'
import ForestViewer from '../components/ForestViewer.vue'
import type { TreeNode } from '../types'
import { showPopup } from '../utils/notify'
import { getDescription } from '../utils/errorCodes'
import { loadWorkspace } from '../utils/persistence'
import { STR } from '../locales/zh-CN'

const store = useForestStore()

// Last result summary restored from localStorage
const lastResultSummary = ref<{ treesCount: number; mappingCount: number } | null>(null)

onMounted(() => {
  const ws = loadWorkspace()
  if (ws.lastDatabase) {
    const perDb = ws.perDatabase[ws.lastDatabase]
    if (perDb?.lastComputeSummary) {
      lastResultSummary.value = {
        treesCount: perDb.lastComputeSummary.trees_count,
        mappingCount: perDb.lastComputeSummary.mapping_count,
      }
      const resultTimestamp = perDb.lastComputeSummary.timestamp
      if (resultTimestamp) {
        const resultAge = Date.now() - new Date(resultTimestamp).getTime()
        const isStale = resultAge > 24 * 60 * 60 * 1000
        if (isStale) {
          const hoursOld = Math.floor(resultAge / (60 * 60 * 1000))
          ElMessage.warning(`计算结果已 ${hoursOld} 小时未更新，建议重新计算以确保结果最新`)
        }
      }
    }
  }
  // Fetch visualization if trees already loaded (e.g. navigated from ComputePrepPage)
  if (store.trees.length > 0) {
    fetchVisualizationWithFilter()
  }
})

// Watch trees changes (e.g. after compute completes)
watch(() => store.trees.length, () => {
  if (store.trees.length > 0) {
    fetchVisualizationWithFilter()
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
const showMinimap = ref(false)
const showDrawer = ref(false)

const forestViewerRef = ref<InstanceType<typeof ForestViewer> | null>(null)

function resetView() { forestViewerRef.value?.resetView() }
function toggleMinimap() { showMinimap.value = !showMinimap.value }

function getFilteredTrees(): TreeNode[] {
  if (!showBranchingOnly.value) return store.trees
  return store.trees.filter(t => t.resolved_state === 'pending')
}

const hasBranchingTrees = computed(() => store.trees.some(t => t.resolved_state === 'pending'))

const emptyMessage = computed(() => {
  if (store.trees.length === 0) {
    if (lastResultSummary.value) {
      return `上次计算结果：${lastResultSummary.value.treesCount} 棵树，${lastResultSummary.value.mappingCount} 个映射。请在计算准备页点击"▶️ 开始计算"。`
    }
    return STR.forestPage.emptyNoForest
  }
  if (showBranchingOnly.value) {
    return STR.forestPage.emptyNoBranching
  }
  return ''
})

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
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  padding: 4px 0;
  border-bottom: 1px solid var(--el-border-color-light);
}
.forest-top-bar .status-text {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>

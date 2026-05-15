<template>
  <div class="forest-page gui-page">
    <div class="forest-top-bar">
      <div class="forest-controls">
        <el-button size="small" @click="resetView">🔄 重置视图</el-button>
        <el-button size="small" @click="toggleMinimap">📐 小地图</el-button>
        <el-switch
          v-if="store.trees.length > 0 || store.errors.length > 0"
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
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useForestStore } from '../stores/forest'
import ForestViewer from '../components/ForestViewer.vue'
import type { TreeNode } from '../types'
import { showPopup } from '../utils/notify'
import { getDescription } from '../utils/errorCodes'
import { useAppStore } from '../stores/app'
import { STR } from '../locales/zh-CN'

const store = useForestStore()
const appStore = useAppStore()
const route = useRoute()

onMounted(async () => {
  const workspaceId = route.params.workspaceId as string
  if (workspaceId) {
    appStore.setCurrentWorkspaceId(workspaceId)
  }

  // Fetch SVG from workspace API (returns SVG text, Content-Type: image/svg+xml)
  try {
    const svgResp = await fetch(`/api/workspace/${workspaceId}/forest/svg`)
    if (svgResp.ok) {
      store.svgContent = await svgResp.text()
    }
  } catch {
    // SVG not available — user will see empty state
  }

  // Fetch mapping from workspace API (returns JSON)
  try {
    const mappingResp = await fetch(`/api/workspace/${workspaceId}/forest/mapping`)
    if (mappingResp.ok) {
      const mappingData = await mappingResp.json()
      if (mappingData) {
        if (Array.isArray(mappingData.trees)) {
          store.trees = mappingData.trees
        }
        if (Array.isArray(mappingData.final_mapping)) {
          store.finalMapping = mappingData.final_mapping
        }
      }
    }
  } catch {
    // Mapping not available
  }
})

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

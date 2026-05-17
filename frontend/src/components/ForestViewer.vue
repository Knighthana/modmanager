<template>
  <el-card shadow="never" v-loading="store.isRunning">
    <!-- 空状态：无 SVG 且不在加载中 -->
    <div
      v-if="!store.svgContent && !store.isRunning"
      style="text-align: center; padding: 40px; color: #999;"
    >
      {{ props.emptyMessage || STR.forestViewer.emptyFallback }}
    </div>
    <!-- SVG 渲染区 -->
    <div v-if="store.svgContent" class="forest-wrapper">
      <div
        ref="containerRef"
        class="forest-container"
        @mouseover="onMouseOver"
        @mouseout="onMouseOut"
        @click="onNodeClick"
        v-html="store.svgContent"
      />
      <div v-if="store.trees.length > 0" class="forest-status-overlay" @click="toggleStatusBar">
        📋 {{ store.errors.length + store.warnings.length }}
        <span v-if="showStatusDetail">
          &nbsp;{{ store.trees.length }} 树 {{ store.finalMapping.length }} 映射 {{ store.warnings.length }} 警告 {{ store.errors.length }} 错误
        </span>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useForestStore } from '../stores/forest'
import { useAppStore } from '../stores/app'
import { STR } from '../locales/zh-CN'

const props = defineProps<{
    emptyMessage?: string
}>()

const store = useForestStore()
const appStore = useAppStore()

const selectedTreeRoot = ref<string | null>(null)
const showStatusDetail = ref(true)

// Restore from persistent storage
showStatusDetail.value = appStore.load<boolean>('forest.statusBarExpanded') ?? true

function toggleStatusBar() {
  showStatusDetail.value = !showStatusDetail.value
  appStore.save('forest.statusBarExpanded', showStatusDetail.value)
}

const containerRef = ref<HTMLElement>()

function onMouseOver(e: MouseEvent) {
    const target = e.target as HTMLElement
    const nodeEl = target.closest('[data-tree-node]') as HTMLElement | null
    if (!nodeEl || !containerRef.value) return

    const rootPath = nodeEl.getAttribute('data-tree-node')!
    const refs = (nodeEl.getAttribute('data-tree-refs') || '').split(',').filter(Boolean)
    const refby = (nodeEl.getAttribute('data-tree-referenced-by') || '').split(',').filter(Boolean)
    const highlightPaths = new Set([rootPath, ...refs, ...refby])

    containerRef.value.querySelectorAll('[data-tree-node]').forEach(el => {
        (el as HTMLElement).style.opacity = '0.15'
    })
    highlightPaths.forEach(p => {
        const el = containerRef.value?.querySelector(`[data-tree-node="${CSS.escape(p)}"]`)
        if (el) (el as HTMLElement).style.opacity = '1'
    })
}

function onMouseOut() {
    containerRef.value?.querySelectorAll('[data-tree-node]').forEach(el => {
        (el as HTMLElement).style.opacity = '1'
    })
}

function clearSelection() {
    if (selectedTreeRoot.value && containerRef.value) {
        const el = containerRef.value.querySelector(`[data-tree-node="${CSS.escape(selectedTreeRoot.value)}"]`)
        if (el) el.classList.remove('selected')
    }
    selectedTreeRoot.value = null
}

function onResetView() {
  // 占位：后续引入 pan/zoom 方案时实现
}

defineExpose({ resetView: onResetView })

function onNodeClick(e: MouseEvent) {
    const target = e.target as HTMLElement
    const nodeEl = target.closest('[data-tree-node]') as HTMLElement | null
    if (!nodeEl) return

    const nodePath = nodeEl.getAttribute('data-tree-node')!
    const isPending = nodeEl.hasAttribute('data-tree-pending')

    if (isPending) {
        if (selectedTreeRoot.value === nodePath) {
            clearSelection()
        } else {
            clearSelection()
            selectedTreeRoot.value = nodePath
            nodeEl.classList.add('selected')
        }
        return
    }

    if (selectedTreeRoot.value) {
        const pendingTree = store.trees.find(t => t.root_path === selectedTreeRoot.value)
        if (pendingTree && pendingTree.candidates?.includes(nodePath)) {
            store.setDecision(selectedTreeRoot.value, nodePath)
            clearSelection()
        }
        return
    }
}
</script>

<style scoped>
.forest-wrapper {
  position: relative;
  flex: 1;
  min-height: 0;
}

.forest-container {
  width: 100%;
  height: 100%;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  overflow: hidden;
  cursor: grab;
  position: relative;
  background: #fafafa;
}

.forest-container :deep(svg) {
  display: block;
  width: 100%;
  height: 100%;
}

:deep([data-tree-node]) {
    transition: opacity 0.15s ease;
}

:deep([data-tree-node].selected) {
    filter: drop-shadow(0 0 8px rgba(59, 130, 246, 0.7));
    stroke: #3b82f6;
    stroke-width: 2;
}

.forest-status-overlay {
  position: absolute;
  bottom: 8px;
  left: 8px;
  z-index: 25;
  background: rgba(255,255,255,0.9);
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 13px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
}
.el-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
:deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>

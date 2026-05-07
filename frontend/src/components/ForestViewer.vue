<template>
  <el-card shadow="never" v-loading="store.isRunning">
    <!-- 空状态：无 SVG 且不在加载中 -->
    <div
      v-if="!store.svgContent && !store.isRunning"
      style="text-align: center; padding: 40px; color: #999;"
    >
      {{ props.emptyMessage || '暂无森林图。请先点击"计算映射"。' }}
    </div>
    <div
      v-if="store.svgContent"
      ref="containerRef"
      class="forest-container"
      @wheel.prevent="onWheel"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @mouseleave="onMouseUp"
      @mouseover="onMouseOver"
      @mouseout="onMouseOut"
      @click="onNodeClick"
    >
      <div
        class="forest-svg"
        :style="svgStyle"
        v-html="store.svgContent"
      />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useForestStore } from '../stores/forest'

const props = defineProps<{
    emptyMessage?: string
}>()

const store = useForestStore()
const router = useRouter()

const containerRef = ref<HTMLElement>()
const scale = ref(1)
const offset = ref({ x: 0, y: 0 })
const isDragging = ref(false)
const lastPos = ref({ x: 0, y: 0 })
const selectedTreeRoot = ref<string | null>(null)

function onMouseOver(e: MouseEvent) {
    const target = e.target as HTMLElement
    const nodeEl = target.closest('[data-tree-node]') as HTMLElement | null
    if (!nodeEl) return

    const rootPath = nodeEl.getAttribute('data-tree-node')!
    const refs = (nodeEl.getAttribute('data-tree-refs') || '').split(',').filter(Boolean)
    const refby = (nodeEl.getAttribute('data-tree-referenced-by') || '').split(',').filter(Boolean)
    const highlightPaths = new Set([rootPath, ...refs, ...refby])

    // 所有节点变暗
    containerRef.value?.querySelectorAll('[data-tree-node]').forEach(el => {
        (el as HTMLElement).style.opacity = '0.15'
    })
    // 高亮相关节点
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
    if (selectedTreeRoot.value) {
        const el = containerRef.value?.querySelector(`[data-tree-node="${CSS.escape(selectedTreeRoot.value)}"]`)
        if (el) el.classList.remove('selected')
    }
    selectedTreeRoot.value = null
}

const svgStyle = computed(() => ({
  transform: `scale(${scale.value}) translate(${offset.value.x}px, ${offset.value.y}px)`,
  transformOrigin: '0 0',
}))

function onWheel(e: WheelEvent) {
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  const newScale = scale.value * delta
  if (newScale < 0.1 || newScale > 5) return
  scale.value = newScale
}

function onMouseDown(e: MouseEvent) {
  isDragging.value = true
  lastPos.value = { x: e.clientX, y: e.clientY }
}

function onMouseMove(e: MouseEvent) {
  if (!isDragging.value) return
  const dx = e.clientX - lastPos.value.x
  const dy = e.clientY - lastPos.value.y
  offset.value = {
    x: offset.value.x + dx / scale.value,
    y: offset.value.y + dy / scale.value,
  }
  lastPos.value = { x: e.clientX, y: e.clientY }
}

function onMouseUp() {
  isDragging.value = false
}

function onNodeClick(e: MouseEvent) {
    if (isDragging.value) return
    const target = e.target as HTMLElement
    const nodeEl = target.closest('[data-tree-node]') as HTMLElement | null
    if (!nodeEl) return

    const nodePath = nodeEl.getAttribute('data-tree-node')!
    const isPending = nodeEl.hasAttribute('data-tree-pending')

    if (isPending) {
        if (selectedTreeRoot.value === nodePath) {
            // 取消选中
            clearSelection()
        } else {
            // 进入选枝模式
            clearSelection()
            selectedTreeRoot.value = nodePath
            nodeEl.classList.add('selected')
        }
        return
    }

    // 非 pending 树：若处于选枝模式，尝试作为候选源
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
.forest-container {
  width: 100%;
  min-height: 500px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  overflow: hidden;
  cursor: grab;
  position: relative;
  background: #fafafa;
}

.forest-container:active {
  cursor: grabbing;
}

.forest-svg {
  transition: transform 0.05s ease;
}

:deep([data-tree-node]) {
    transition: opacity 0.15s ease;
}

:deep([data-tree-node].selected) {
    filter: drop-shadow(0 0 8px rgba(59, 130, 246, 0.7));
    stroke: #3b82f6;
    stroke-width: 2;
}
</style>

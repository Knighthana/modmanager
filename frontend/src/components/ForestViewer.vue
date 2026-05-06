<template>
  <el-card shadow="never" v-loading="store.isRunning">
    <!-- 空状态：无 SVG 且不在加载中 -->
    <div
      v-if="!store.svgContent && !store.isRunning"
      style="text-align: center; padding: 40px; color: #999;"
    >
      暂无森林图。请先点击"计算映射"。
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

const store = useForestStore()
const router = useRouter()

const containerRef = ref<HTMLElement>()
const scale = ref(1)
const offset = ref({ x: 0, y: 0 })
const isDragging = ref(false)
const lastPos = ref({ x: 0, y: 0 })

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
  // Ignore clicks during drag
  if (isDragging.value) return
  const target = e.target as HTMLElement
  const nodeEl = target.closest('[data-tree-node]') as HTMLElement | null
  if (!nodeEl) return

  const nodePath = nodeEl.getAttribute('data-tree-node')!
  const isPendingTree = nodeEl.hasAttribute('data-tree-pending')

  if (isPendingTree) {
    router.push({ name: 'conflicts', query: { root_path: nodePath } })
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
</style>

<template>
  <el-card shadow="never" v-loading="store.isRunning">
    <!-- 空状态：无 SVG 且不在加载中 -->
    <div
      v-if="!store.svgContent && !store.isRunning"
      style="text-align: center; padding: 40px; color: #999;"
    >
      {{ props.emptyMessage || STR.forestViewer.emptyFallback }}
    </div>
    <!-- Wrapper: 容器 + 小地图 overlay -->
    <div v-if="store.svgContent" class="forest-wrapper">
      <div
        ref="containerRef"
        class="forest-container"
        :style="{ height: containerHeight + 'px' }"
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
      <div v-if="panZoomReady" class="forest-minimap"
           :style="{ width: minimapSize.w + 'px', height: minimapSize.h + 'px' }"
           @mousedown.stop
           @click.stop="onMinimapClick">
        <div class="forest-minimap-area" />
        <div v-if="minimapViewport" class="forest-minimap-viewport"
             :style="{
               left: minimapViewport.x + 'px',
               top: minimapViewport.y + 'px',
               width: minimapViewport.w + 'px',
               height: minimapViewport.h + 'px',
             }" />
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useForestStore } from '../stores/forest'
import { loadWorkspace, saveWorkspace } from '../utils/persistence'
import { STR } from '../locales/zh-CN'
import svgPanZoom from 'svg-pan-zoom'

const props = defineProps<{
    emptyMessage?: string
}>()

const store = useForestStore()
const router = useRouter()

const containerRef = ref<HTMLElement>()
const containerHeight = ref(window.innerHeight - 120) // nearly full viewport
const selectedTreeRoot = ref<string | null>(null)
const didPan = ref(false)
const minimapSize = ref({ w: 180, h: 120 })
let svgViewBox: { w: number; h: number } | null = null
const minimapViewport = ref<{ x: number; y: number; w: number; h: number } | null>(null)
const panZoomReady = ref(false)
const showStatusDetail = ref(true) // expanded by default per design

// Restore from workspace
try {
  const ws = loadWorkspace()
  if (ws.uiState?.forest?.statusBarExpanded !== undefined) {
    showStatusDetail.value = ws.uiState.forest.statusBarExpanded
  }
} catch { /* ignore */ }

function toggleStatusBar() {
  showStatusDetail.value = !showStatusDetail.value
  try {
    const ws = loadWorkspace()
    if (!ws.uiState) ws.uiState = {}
    if (!ws.uiState.forest) ws.uiState.forest = {}
    ws.uiState.forest.statusBarExpanded = showStatusDetail.value
    saveWorkspace(ws)
  } catch { /* ignore */ }
}

let panZoomInstance: SvgPanZoom.Instance | null = null

function parseSvgViewBox(svg: string): { w: number; h: number } | null {
  const m = svg.match(/viewBox=["']([^"']+)["']/)
  if (!m) return null
  const parts = m[1].split(/\s+/)
  if (parts.length !== 4) return null
  return { w: parseFloat(parts[2]), h: parseFloat(parts[3]) }
}

function initPanZoom() {
  destroyPanZoom()

  const svgEl = containerRef.value?.querySelector('svg')
  if (!svgEl) return

  const vb = parseSvgViewBox(store.svgContent)
  svgViewBox = vb

  // minZoom = container fits entire SVG
  const containerW = containerRef.value?.clientWidth || 800
  const containerH = containerRef.value?.clientHeight || 600
  const fitZoom = vb ? Math.min(containerW / vb.w, containerH / vb.h) : 0.1

  panZoomInstance = svgPanZoom(svgEl, {
    fit: true,
    center: true,
    minZoom: fitZoom,
    maxZoom: 500,
    zoomScaleSensitivity: 0.5,
    controlIconsEnabled: false,
    dblClickZoomEnabled: true,
    mouseWheelZoomEnabled: true,
    beforePan: () => { didPan.value = true },
    onPan: () => { minimapViewport.value = computeMinimapViewport() },
    onZoom: () => { minimapViewport.value = computeMinimapViewport() },
  })

  // 初始计算一次
  minimapViewport.value = computeMinimapViewport()
  panZoomReady.value = true
}

function destroyPanZoom() {
  if (panZoomInstance) {
    panZoomInstance.destroy()
    panZoomInstance = null
  }
  panZoomReady.value = false
}

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

function onResetView() {
  if (!panZoomInstance) return
  panZoomInstance.fit()
  panZoomInstance.center()
  didPan.value = false
}

defineExpose({ resetView: onResetView })

function computeMinimapViewport(): { x: number; y: number; w: number; h: number } | null {
  if (!panZoomInstance || !svgViewBox) return null
  const zoom = panZoomInstance.getZoom()
  const pan  = panZoomInstance.getPan()
  const sizes = panZoomInstance.getSizes()

  const cw = sizes.width
  const ch = sizes.height

  const visW = cw / zoom
  const visH = ch / zoom

  const centerX = svgViewBox.w / 2 - pan.x / zoom
  const centerY = svgViewBox.h / 2 - pan.y / zoom

  const visX = centerX - visW / 2
  const visY = centerY - visH / 2

  const mmW = minimapSize.value.w
  const mmH = minimapSize.value.h
  const scale = Math.min(mmW / svgViewBox.w, mmH / svgViewBox.h)

  return {
    x: visX * scale,
    y: visY * scale,
    w: visW * scale,
    h: visH * scale,
  }
}

function onMinimapClick(e: MouseEvent) {
  if (!panZoomInstance || !svgViewBox) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top

  // 将点击位置映射到 SVG 坐标系
  const svgX = (mx / minimapSize.value.w) * svgViewBox.w
  const svgY = (my / minimapSize.value.h) * svgViewBox.h

  // 计算 pan 值，使点击位置成为视口几何中心
  // centerX = svgViewBox.w/2 - pan.x/zoom  →  pan.x = (svgViewBox.w/2 - svgX) * zoom
  const zoom = panZoomInstance.getZoom()
  const targetPanX = (svgViewBox.w / 2 - svgX) * zoom
  const targetPanY = (svgViewBox.h / 2 - svgY) * zoom

  panZoomInstance.pan({ x: targetPanX, y: targetPanY })
}

watch(() => store.svgContent, async (newVal) => {
  if (!newVal) {
    destroyPanZoom()
    return
  }

  await nextTick()
  await new Promise(resolve => requestAnimationFrame(resolve))

  initPanZoom()
})

let ro: ResizeObserver | null = null

onMounted(() => {
  const updateHeight = () => { containerHeight.value = window.innerHeight - 180 }
  window.addEventListener('resize', updateHeight)

  if (containerRef.value) {
    ro = new ResizeObserver(() => {
      if (panZoomInstance) {
        panZoomInstance.resize()
        panZoomInstance.fit()
        minimapViewport.value = computeMinimapViewport()
      }
    })
    ro.observe(containerRef.value)
  }
})

onUnmounted(() => {
  destroyPanZoom()
  ro?.disconnect()
})

function onNodeClick(e: MouseEvent) {
    // 拖拽平移后不触发 click
    if (didPan.value) {
      didPan.value = false
      return
    }
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
.forest-wrapper {
  position: relative;
}

.forest-container {
  width: 100%;
  height: 100px;
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

.forest-toolbar {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  margin-bottom: 4px;
}

.forest-minimap {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(250, 250, 250, 0.8);
  border: 1px solid #d1d5db;
  border-radius: 4px;
  overflow: hidden;
  z-index: 10;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.forest-minimap-area {
  position: absolute;
  inset: 2px;
  border: 1px solid #94a3b8;
  background: #f8fafc;
  border-radius: 2px;
  pointer-events: none;
}

.forest-minimap-viewport {
  position: absolute;
  border: 1.5px solid #3b82f6;
  background: rgba(59, 130, 246, 0.12);
  pointer-events: none;
  border-radius: 2px;
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
</style>

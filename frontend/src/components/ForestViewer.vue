<template>
  <el-card shadow="never" v-loading="store.isRunning">
    <!-- 空状态：无 SVG 且不在加载中 -->
    <div
      v-if="!store.svgContent && !store.isRunning"
      style="text-align: center; padding: 40px; color: #999;"
    >
      {{ props.emptyMessage || STR.forestViewer.emptyFallback }}
    </div>
    <div v-if="store.svgContent" class="forest-toolbar">
      <el-button size="small" @click="onResetView">
        {{ STR.forestViewer.resetView }}
      </el-button>
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
      <div v-if="panZoomReady" class="forest-minimap"
           :style="{ width: minimapSize.w + 'px', height: minimapSize.h + 'px' }"
           @mousedown.stop
           @click.stop="onMinimapClick">
        <!-- 全图区域矩形 -->
        <div class="forest-minimap-area" />
        <!-- 视口矩形 -->
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
import { useRouter } from 'vue-router'
import { useForestStore } from '../stores/forest'
import { STR } from '../locales/zh-CN'
import svgPanZoom from 'svg-pan-zoom'

const props = defineProps<{
    emptyMessage?: string
}>()

const store = useForestStore()
const router = useRouter()

const containerRef = ref<HTMLElement>()
const containerHeight = ref(500)
const selectedTreeRoot = ref<string | null>(null)
const didPan = ref(false)
const minimapSize = ref({ w: 180, h: 120 })
let svgViewBox: { w: number; h: number } | null = null
const minimapViewport = ref<{ x: number; y: number; w: number; h: number } | null>(null)
const panZoomReady = ref(false)

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

  panZoomInstance = svgPanZoom(svgEl, {
    fit: true,
    center: true,
    minZoom: 0.1,
    maxZoom: 5,
    zoomScaleSensitivity: 0.2,
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
  const sx = mmW / svgViewBox.w
  const sy = mmH / svgViewBox.h

  return {
    x: visX * sx,
    y: visY * sy,
    w: visW * sx,
    h: visH * sy,
  }
}

function onMinimapClick(e: MouseEvent) {
  if (!panZoomInstance || !svgViewBox) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top

  const svgX = (mx / minimapSize.value.w) * svgViewBox.w
  const svgY = (my / minimapSize.value.h) * svgViewBox.h

  const sizes = panZoomInstance.getSizes()
  const zoom = panZoomInstance.getZoom()
  const targetPanX = -(svgX - svgViewBox.w / 2) * zoom + sizes.width / 2
  const targetPanY = -(svgY - svgViewBox.h / 2) * zoom + sizes.height / 2

  panZoomInstance.pan({ x: targetPanX, y: targetPanY })
}

watch(() => store.svgContent, async (newVal) => {
  if (!newVal) {
    destroyPanZoom()
    containerHeight.value = 500
    return
  }

  // 等待 v-html 渲染
  await nextTick()
  // 等待浏览器完成布局（确保 clientWidth 可用）
  await new Promise(resolve => requestAnimationFrame(resolve))

  // 确保 ResizeObserver 在容器首次出现时被创建
  if (!ro && containerRef.value) {
    ro = new ResizeObserver(() => {
      const vb2 = store.svgContent ? parseSvgViewBox(store.svgContent) : null
      if (vb2 && containerRef.value) {
        const cw2 = containerRef.value.clientWidth
        if (cw2 > 0) {
          containerHeight.value = Math.max((cw2 / vb2.w) * vb2.h, 100)
        }
      }
      if (panZoomInstance) {
        panZoomInstance.resize()
        panZoomInstance.fit()
        minimapViewport.value = computeMinimapViewport()
      }
    })
    ro.observe(containerRef.value)
  }

  // 现在 clientWidth 是准确的
  const vb = parseSvgViewBox(newVal)
  if (vb && containerRef.value) {
    const cw = containerRef.value.clientWidth
    if (cw > 0) {
      containerHeight.value = Math.max((cw / vb.w) * vb.h, 100)
    }
  }

  // 等待高度生效
  await nextTick()

  initPanZoom()
})

let ro: ResizeObserver | null = null

onMounted(() => {
  if (containerRef.value) {
    ro = new ResizeObserver(() => {
      // 容器宽度变化 → 重新计算高度 + 适配
      const vb = store.svgContent ? parseSvgViewBox(store.svgContent) : null
      if (vb && containerRef.value) {
        const cw = containerRef.value.clientWidth
        if (cw > 0) {
          containerHeight.value = Math.max((cw / vb.w) * vb.h, 100)
        }
      }
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
</style>

<template>
  <el-card shadow="never" v-loading="store.isRunning">
    <div
      v-if="!store.svgContent && !store.isRunning"
      style="text-align: center; padding: 40px; color: #999;"
    >
      {{ props.emptyMessage || STR.forestViewer.emptyFallback }}
    </div>
    <div v-if="store.svgContent" class="forest-wrapper">
      <div
        ref="containerRef"
        class="forest-container"
        :class="{ dragging: isDragging }"
        @mousedown="onContainerMouseDown"
        @mouseover="onMouseOver"
        @mouseout="onMouseOut"
        @click="onNodeClick"
      >
        <!-- 小地图浮层 -->
        <div
          v-if="showMinimap && minimapReady"
          class="forest-minimap"
          :style="{ width: minimapWidth + 'px', height: minimapHeight + 'px' }"
          @mousedown.stop="onMinimapMouseDown"
        >
          <div class="forest-minimap-locator" :style="locatorStyle" />
        </div>
      </div>
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
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useForestStore } from '../stores/forest'
import { useAppStore } from '../stores/app'
import { STR } from '../locales/zh-CN'
import svgPanZoom from 'svg-pan-zoom'

const props = defineProps<{
    emptyMessage?: string
    showMinimap?: boolean
}>()

const store = useForestStore()
const appStore = useAppStore()

const containerRef = ref<HTMLElement>()
const selectedTreeRoot = ref<string | null>(null)
const showStatusDetail = ref(true)
const didPan = ref(false)

const minimapReady = ref(false)
const minimapWidth = ref(0)
const minimapHeight = ref(0)
const locatorStyle = ref<Record<string, string>>({})

showStatusDetail.value = appStore.load<boolean>('forest.statusBarExpanded') ?? true

function toggleStatusBar() {
  showStatusDetail.value = !showStatusDetail.value
  appStore.save('forest.statusBarExpanded', showStatusDetail.value)
}

// ── svg-pan-zoom ────────────────────────────────────────────────────────

let panZoomInstance: SvgPanZoom.Instance | null = null
let isPointerDown = false
let isDragging = false
let dragStartX = 0
let dragStartY = 0
let dragLastX = 0
let dragLastY = 0

const MIN_ZOOM_RELATIVE_TO_FIT = 1

function parseSvgViewBox(svg: string): { w: number; h: number } | null {
  const m = svg.match(/viewBox=["']([^"']+)["']/)
  if (!m) return null
  const parts = m[1].split(/\s+/)
  if (parts.length !== 4) return null
  return { w: parseFloat(parts[2]), h: parseFloat(parts[3]) }
}

function updateMinimap() {
  if (!panZoomInstance || !containerRef.value) return
  const sizes = panZoomInstance.getSizes()
  const pan = panZoomInstance.getPan()

  const svgW = sizes.viewBox.width
  const svgH = sizes.viewBox.height
  const svgAspectRatio = svgH / svgW

  const containerH = containerRef.value.clientHeight

  // 小地图高度不超过容器的 40%，且绝对上限 250px
  const maxMapH = Math.min(250, containerH * 0.4)
  let mapH = maxMapH
  let mapW = mapH / svgAspectRatio

  // 极端竖长图防御：宽度低于 50px 则保底
  if (mapW < 50) {
    mapW = 50
    mapH = mapW * svgAspectRatio
  }
  // 高度回缩防御
  if (mapH > containerH - 40) {
    mapH = containerH - 40
    mapW = mapH / svgAspectRatio
  }

  minimapWidth.value = mapW
  minimapHeight.value = mapH

  const renderedW = svgW * sizes.realZoom
  const renderedH = svgH * sizes.realZoom

  const leftPct = -pan.x / renderedW
  const topPct = -pan.y / renderedH
  const widthPct = sizes.width / renderedW
  const heightPct = sizes.height / renderedH

  locatorStyle.value = {
    left: Math.max(0, leftPct * mapW) + 'px',
    top: Math.max(0, topPct * mapH) + 'px',
    width: Math.min(mapW, widthPct * mapW) + 'px',
    height: Math.min(mapH, heightPct * mapH) + 'px',
  }
}

function onMinimapMouseDown(e: MouseEvent) {
  e.preventDefault()
  moveMainViewToMinimap(e.clientX, e.clientY)

  const onMove = (ev: MouseEvent) => moveMainViewToMinimap(ev.clientX, ev.clientY)
  const onUp = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

function moveMainViewToMinimap(clientX: number, clientY: number) {
  if (!panZoomInstance) return
  const minimap = containerRef.value?.querySelector('.forest-minimap') as HTMLElement
  if (!minimap) return
  const rect = minimap.getBoundingClientRect()
  let mx = clientX - rect.left
  let my = clientY - rect.top
  mx = Math.max(0, Math.min(rect.width, mx))
  my = Math.max(0, Math.min(rect.height, my))

  const pctX = mx / rect.width
  const pctY = my / rect.height

  const sizes = panZoomInstance.getSizes()
  const renderedW = sizes.viewBox.width * sizes.realZoom
  const renderedH = sizes.viewBox.height * sizes.realZoom

  const newPanX = sizes.width / 2 - pctX * renderedW
  const newPanY = sizes.height / 2 - pctY * renderedH

  panZoomInstance.pan({ x: newPanX, y: newPanY })
}

function initPanZoom() {
  destroyPanZoom()

  const svgEl = containerRef.value?.querySelector('svg')
  if (!svgEl) return

  const vb = parseSvgViewBox(store.svgContent)
  const cw = containerRef.value?.clientWidth || 800
  const ch = containerRef.value?.clientHeight || 600
  // Diagnostic only: do not pass this absolute value into minZoom/maxZoom.
  const originalViewportZoomDiagnostic = vb ? Math.min(cw / vb.w, ch / vb.h) : 0.5
  if (import.meta.env.DEV) {
    console.debug('Diagnostic original viewport zoom (do not use for config):', originalViewportZoomDiagnostic)
  }

  panZoomInstance = svgPanZoom(svgEl, {
    panEnabled: false,
    zoomEnabled: true,
    controlIconsEnabled: false,
    fit: true,
    center: true,
    // Keep lower bound at fitted state. See repo_memo/FRONTEND_INTEGRATION_CONSTRAINTS.md.
    minZoom: MIN_ZOOM_RELATIVE_TO_FIT,
    maxZoom: 80,
    onZoom: updateMinimap,
    onPan: updateMinimap,
    beforePan(oldPan, newPan) {
      const self = (this as unknown as SvgPanZoom.Instance)
      const sizes = self.getSizes()
      const renderedW = sizes.viewBox.width * sizes.realZoom
      const renderedH = sizes.viewBox.height * sizes.realZoom

      let tx = newPan.x
      let ty = newPan.y

      if (renderedW > sizes.width) {
        const minX = sizes.width - renderedW
        tx = Math.max(minX, Math.min(0, newPan.x))
      } else {
        tx = (sizes.width - renderedW) / 2
      }
      if (renderedH > sizes.height) {
        const minY = sizes.height - renderedH
        ty = Math.max(minY, Math.min(0, newPan.y))
      } else {
        ty = (sizes.height - renderedH) / 2
      }

      return { x: tx, y: ty }
    },
  })

  // 延时强力刷新，规避容器尺寸未就绪的竞态
  setTimeout(() => {
    if (panZoomInstance) {
      panZoomInstance.resize()
      panZoomInstance.fit()
      panZoomInstance.center()
      updateMinimap()
    }
  }, 60)

  updateMinimap()
  minimapReady.value = true
}

function destroyPanZoom() {
  if (panZoomInstance) {
    panZoomInstance.destroy()
    panZoomInstance = null
  }
  minimapReady.value = false
}

// ── 自定义拖拽（3px 阈值 + 文字保护）──────────────────────────────────────

function onContainerMouseDown(e: MouseEvent) {
  if ((e.target as HTMLElement).closest('.forest-minimap')) return
  isPointerDown = true
  isDragging = false
  dragStartX = e.clientX
  dragStartY = e.clientY
  dragLastX = e.clientX
  dragLastY = e.clientY
}

function onWindowMouseMove(e: MouseEvent) {
  if (!isPointerDown || !panZoomInstance) return

  if (!isDragging) {
    const dist = Math.sqrt((e.clientX - dragStartX) ** 2 + (e.clientY - dragStartY) ** 2)
    if (dist <= 3) return
    const tag = (e.target as HTMLElement).tagName?.toLowerCase()
    if (tag === 'text' || tag === 'tspan' || tag === 'a' || (e.target as HTMLElement).closest('a')) {
      isPointerDown = false
      return
    }
    isDragging = true
    didPan.value = true
  }

  e.preventDefault()
  const deltaX = e.clientX - dragLastX
  const deltaY = e.clientY - dragLastY

  const currentPan = panZoomInstance.getPan()
  panZoomInstance.pan({
    x: currentPan.x + deltaX,
    y: currentPan.y + deltaY,
  })

  dragLastX = e.clientX
  dragLastY = e.clientY
}

function onWindowMouseUp() {
  isPointerDown = false
  isDragging = false
}

// ── 树节点交互 ──────────────────────────────────────────────────────────

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
  if (!panZoomInstance) return
  panZoomInstance.fit()
  panZoomInstance.center()
  didPan.value = false
  updateMinimap()
}

defineExpose({ resetView: onResetView })

function onNodeClick(e: MouseEvent) {
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

// ── SVG 预处理 ──────────────────────────────────────────────────────────

function preprocessAndInsertSvg(svgText: string): boolean {
  if (!containerRef.value) return false

  // 移除旧 SVG
  containerRef.value.querySelector('svg')?.remove()

  try {
    const parser = new DOMParser()
    const doc = parser.parseFromString(svgText, 'image/svg+xml')
    const svgEl = doc.querySelector('svg')
    if (!svgEl || doc.querySelector('parsererror')) throw new Error('parse failed')

    if (!svgEl.hasAttribute('viewBox')) {
      let w = parseFloat(svgEl.getAttribute('width') || '')
      let h = parseFloat(svgEl.getAttribute('height') || '')
      if (isNaN(w) || isNaN(h)) { w = 2000; h = 2000 }
      svgEl.setAttribute('viewBox', `0 0 ${w} ${h}`)
    }
    svgEl.setAttribute('width', '100%')
    svgEl.setAttribute('height', '100%')

    containerRef.value.appendChild(svgEl)
    return true
  } catch {
    // 回退
    containerRef.value.insertAdjacentHTML('beforeend', svgText)
    const svgEl = containerRef.value.querySelector('svg')
    if (svgEl) {
      svgEl.setAttribute('width', '100%')
      svgEl.setAttribute('height', '100%')
    }
    return !!svgEl
  }
}

// ── 生命周期 ────────────────────────────────────────────────────────────

watch(() => store.svgContent, async (newVal) => {
  if (!newVal) {
  containerRef.value?.removeEventListener('mousedown', onContainerMouseDown)
  destroyPanZoom()
    return
  }
  await nextTick()
  if (!preprocessAndInsertSvg(newVal)) return
  await new Promise(resolve => requestAnimationFrame(resolve))
  initPanZoom()
}, { immediate: true })

let ro: ResizeObserver | null = null

onMounted(() => {
  document.addEventListener('mousemove', onWindowMouseMove)
  document.addEventListener('mouseup', onWindowMouseUp)

  if (containerRef.value) {
    ro = new ResizeObserver(() => {
      if (panZoomInstance) {
        panZoomInstance.resize()
        panZoomInstance.fit()
        panZoomInstance.center()
        updateMinimap()
      }
    })
    ro.observe(containerRef.value)
  }
})

onUnmounted(() => {
  document.removeEventListener('mousemove', onWindowMouseMove)
  document.removeEventListener('mouseup', onWindowMouseUp)
  destroyPanZoom()
  ro?.disconnect()
})
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
  position: relative;
  background: #fafafa;
}

.forest-container :deep(svg) {
  cursor: grab;
}
.forest-container.dragging :deep(svg) {
  cursor: grabbing !important;
}
.forest-container :deep(svg) :is(text, tspan) {
  cursor: text !important;
  user-select: text !important;
  -webkit-user-select: text !important;
}
.forest-container :deep(svg) a {
  cursor: pointer !important;
}

:deep([data-tree-node]) {
    transition: opacity 0.15s ease;
}

:deep([data-tree-node].selected) {
    filter: drop-shadow(0 0 8px rgba(59, 130, 246, 0.7));
    stroke: #3b82f6;
    stroke-width: 2;
}

/* ── 小地图（尺寸完全由 JS 动态注入，CSS 不插手宽高）── */
.forest-minimap {
  position: absolute;
  top: 8px;
  left: 8px;
  background: rgba(250, 250, 250, 0.85);
  border: 1px solid #94a3b8;
  border-radius: 4px;
  overflow: hidden;
  z-index: 10;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.forest-minimap-locator {
  position: absolute;
  border: 2px solid #3b82f6;
  background: rgba(59, 130, 246, 0.12);
  pointer-events: none;
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

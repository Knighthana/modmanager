# 方案迁移: CSS transform → svg-pan-zoom

> 状态: 已实现
> 目标文件: `ForestViewer.vue`（重写）、`package.json`（新增依赖）

---

## 一、迁移动因

当前 CSS `transform: scale() translate()` 方案有三个固有问题：

| 问题 | 根因 | svg-pan-zoom 如何解决 |
|------|------|----------------------|
| 非整数倍缩放模糊 | CSS transform 是位图缩放 | 操作 SVG `viewBox` — 始终矢量重绘 |
| 事件坐标需换算 | CSS transform 不变更布局，`clientX/Y` 对应屏幕坐标非 SVG 坐标 | viewBox 操作后鼠标坐标直接对应 SVG 坐标系 |
| 手写 ~100 行缩放/平移/自适应 | 自建 zoom/pan/drag/fit/resize | 内置 `fit`/`resize`/`pan`/`zoom` API |

---

## 二、删除清单

以下全部从 `ForestViewer.vue` 删除：

### state (ref)
- `scale`、`offset`、`isDragging`、`lastPos`、`containerWidth`、`userAdjustedScale`、`lastAutoFitScale`、`containerHeight`

### computed
- `svgStyle`

### 函数
- `getSvgNaturalWidth()`、`fitToContainer()`、`updateContainerHeight()`
- `onWheel()`、`onMouseDown()`、`onMouseMove()`、`onMouseUp()`

### 模板事件绑定
- `@wheel.prevent`、`@mousedown`、`@mousemove`、`@mouseup`、`@mouseleave`

### 模板结构
- `.forest-svg` 包裹 div 及其 `:style="svgStyle"` — 改为 `v-html` 直接挂在 `.forest-container` 上

### CSS
- `.forest-svg` 规则（transition 等）

### 其他
- ResizeObserver 中的 `if (!userAdjustedScale)` 分支（改为直接调 `resize()` + `fit()`）

---

## 三、新增清单

### 3.1 依赖

```bash
cd frontend && npm install svg-pan-zoom
```

### 3.2 新增 state

```typescript
// svg-pan-zoom 实例引用
let panZoomInstance: SvgPanZoom.Instance | null = null

// 当前容器高度（根据 SVG 宽高比动态计算）
const containerHeight = ref(500)

// 用户是否正在拖拽平移（用于抑制 click 事件）
const didPan = ref(false)
```

### 3.3 新增函数

#### `parseSvgViewBox(svgString)` — 从 SVG 字符串提取 viewBox

```typescript
function parseSvgViewBox(svg: string): { w: number; h: number } | null {
  const m = svg.match(/viewBox=["']([^"']+)["']/)
  if (!m) return null
  const parts = m[1].split(/\s+/)
  if (parts.length !== 4) return null
  return { w: parseFloat(parts[2]), h: parseFloat(parts[3]) }
}
```

#### `initPanZoom()` — 初始化 svg-pan-zoom

```typescript
function initPanZoom() {
  destroyPanZoom()
  
  const svgEl = containerRef.value?.querySelector('svg')
  if (!svgEl) return
  
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
  })
}
```

#### `destroyPanZoom()` — 销毁旧实例

```typescript
function destroyPanZoom() {
  if (panZoomInstance) {
    panZoomInstance.destroy()
    panZoomInstance = null
  }
}
```

### 3.4 生命周期修改

#### watch svgContent

```typescript
watch(() => store.svgContent, async (newVal) => {
  if (!newVal) {
    destroyPanZoom()
    containerHeight.value = 500
    return
  }
  
  // 从字符串提取 viewBox，计算容器高度
  const vb = parseSvgViewBox(newVal)
  if (vb) {
    const cw = containerRef.value?.clientWidth ?? 0
    if (cw > 0) {
      containerHeight.value = Math.max((cw / vb.w) * vb.h, 100)
    }
  }
  
  // 等待 v-html 渲染 + 高度生效
  await nextTick()
  await nextTick()
  
  initPanZoom()
})
```

#### ResizeObserver

```typescript
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
      }
    })
    ro.observe(containerRef.value)
  }
})

onUnmounted(() => {
  destroyPanZoom()
  ro?.disconnect()
})
```

### 3.5 click 事件中抑制拖拽误触

```typescript
function onNodeClick(e: MouseEvent) {
  if (didPan.value) {
    didPan.value = false
    return
  }
  // ... 原有 click 逻辑不变 ...
}
```

### 3.6 模板改动

```html
<!-- 旧 -->
<div v-if="store.svgContent" ref="containerRef" class="forest-container"
     :style="{ height: containerHeight + 'px' }"
     @wheel.prevent="onWheel"
     @mousedown="onMouseDown" @mousemove="onMouseMove"
     @mouseup="onMouseUp" @mouseleave="onMouseUp"
     @mouseover="onMouseOver" @mouseout="onMouseOut" @click="onNodeClick">
  <div class="forest-svg" :style="svgStyle" v-html="store.svgContent" />
</div>

<!-- 新 -->
<div v-if="store.svgContent" ref="containerRef" class="forest-container"
     :style="{ height: containerHeight + 'px' }"
     @mouseover="onMouseOver" @mouseout="onMouseOut" @click="onNodeClick"
     v-html="store.svgContent">
</div>
```

### 3.7 CSS 改动

`.forest-container` 中：
- `cursor: grab` 保持（svg-pan-zoom 不管理 cursor）
- `overflow: hidden` 保持
- 删除 `.forest-container:active { cursor: grabbing }` 
- 删除 `.forest-svg` 全部规则

---

## 四、保留清单（不变）

| 项目 | 原因 |
|------|------|
| `onMouseOver` / `onMouseOut` | 基于 DOM 属性 `[data-tree-node]` 的高亮逻辑，与缩放机制无关 |
| `onNodeClick` | 同上（仅增加 `didPan` 守卫） |
| `clearSelection` | 同上 |
| `selectedTreeRoot` | 分支决策状态 |
| `containerRef` | 容器 DOM 引用 |
| `store` / `router` / `props` | 外部依赖不变 |
| `:deep([data-tree-node])` 的 CSS 规则 | SVG 元素样式 |

---

## 五、不改动范围

- Python 后端（`forest_visual.py`、`routes/pipeline.py`）— 零改动
- `ForestPage.vue` — 零改动
- `forest.ts` store — 零改动
- 其他前端组件

---

## 六、TypeScript 类型

svg-pan-zoom 包自带 TypeScript 类型声明。实例类型为 `SvgPanZoom.Instance`。

```typescript
import svgPanZoom, { type Instance as PanZoomInstance } from 'svg-pan-zoom'
```

---

## 七、验证要点

1. SVG 首次加载 → 自适应容器宽度，无横向/纵向空白
2. 滚轮缩放 → 以鼠标位置为中心缩放
3. 拖拽平移 → SVG 平滑跟随
4. 双击 → 放大
5. hover 节点 → 关联节点高亮（同之前）
6. click pending 节点 → 进入选枝模式（同之前）
7. 拖拽后 click → 不触发选枝（didPan 守卫）
8. 窗口缩放 → SVG 重新适配
9. 切换显示模式（全部/仅分枝）→ 新 SVG 正确加载
10. 极窄窗口 → minZoom=0.1 生效

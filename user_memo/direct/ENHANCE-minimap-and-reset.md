# 增强: 重置按钮 + 小地图

> 状态: 已实现
> 依赖: svg-pan-zoom 迁移已完成
> 目标文件: `ForestViewer.vue`

---

## 一、布局

```
┌──────────────────────────────────────────────┐
│ 工具栏: [重置视图] [  ..........预留..........  ] │  ← 新增
├──────────────────────────────────────────────┤
│ ┌──────────┐                                 │
│ │  小地图   │                                 │
│ │ ┌────┐   │    主 SVG 视图                    │
│ │ │视口│   │    (svg-pan-zoom 管理)             │
│ │ └────┘   │                                 │
│ └──────────┘                                 │
│                                              │
└──────────────────────────────────────────────┘
```

---

## 二、功能1: 重置按钮

### 模板

在 `.forest-container` 上方新增工具栏行（放在 `v-if="store.svgContent"` 的 div 之前）：

```html
<div v-if="store.svgContent" class="forest-toolbar">
  <el-button size="small" @click="onResetView">
    {{ STR.forestViewer.resetView || '重置视图' }}
  </el-button>
</div>
```

### 逻辑

```typescript
function onResetView() {
  if (!panZoomInstance) return
  panZoomInstance.fit()
  panZoomInstance.center()
  didPan.value = false
}
```

### CSS

```css
.forest-toolbar {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  margin-bottom: 4px;
}
```

### 字符串

如果 `zh-CN.ts` 中没有 `forestViewer.resetView`，暂用硬编码 `'重置视图'`。

---

## 三、功能2: 小地图

### 3.1 核心方案

- 克隆 `store.svgContent` 渲染到 180×120px 小容器
- 用 `position: absolute; top: 8px; left: 8px` 浮在主视图左上角
- 半透明背景
- 视口矩形：从 svg-pan-zoom 的 `getPan()` + `getZoom()` + `getSizes()` 实时计算
- 点击跳转：监听小地图 click，换算为 SVG 坐标后调用 `panZoomInstance.pan()`

### 3.2 关键计算：视口矩形

```typescript
function computeMinimapViewport(): { x: number; y: number; w: number; h: number } | null {
  if (!panZoomInstance || !svgViewBox) return null
  const zoom = panZoomInstance.getZoom()
  const pan  = panZoomInstance.getPan()
  const sizes = panZoomInstance.getSizes()

  // 主视图容器尺寸
  const cw = sizes.width
  const ch = sizes.height

  // 视口在 SVG 坐标中的尺寸
  const visW = cw / zoom
  const visH = ch / zoom

  // 初始 fit 时，整个 SVG 居中显示在容器中
  // fitZoom 时的可视区 = 整个 SVG
  // 当前 zoom > fitZoom 时，可视区缩小
  // pan 记录相对于 fit 位置的偏移

  // 在 fit 状态下，可视区中心 = SVG 中心
  // 偏移后，可视区中心 = SVG中心 + (-pan.x/zoom, -pan.y/zoom)
  // （pan 的正方向对应 SVG 向右下移动，即可视区向左上移动）
  const centerX = svgViewBox.w / 2 - pan.x / zoom
  const centerY = svgViewBox.h / 2 - pan.y / zoom

  // 可视区左上角（SVG 坐标）
  const visX = centerX - visW / 2
  const visY = centerY - visH / 2

  // 缩放到小地图坐标
  const mmW = minimapSize.value.w // 180
  const mmH = minimapSize.value.h // 120
  const sx = mmW / svgViewBox.w
  const sy = mmH / svgViewBox.h

  return {
    x: visX * sx,
    y: visY * sy,
    w: visW * sx,
    h: visH * sy,
  }
}
```

### 3.3 点击跳转

```typescript
function onMinimapClick(e: MouseEvent) {
  if (!panZoomInstance || !svgViewBox) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top

  // 小地图坐标 → SVG 坐标
  const svgX = (mx / minimapSize.value.w) * svgViewBox.w
  const svgY = (my / minimapSize.value.h) * svgViewBox.h

  // 将目标点移到视口中心
  const sizes = panZoomInstance.getSizes()
  const zoom = panZoomInstance.getZoom()
  const targetPanX = -(svgX - svgViewBox.w / 2) * zoom + sizes.width / 2
  const targetPanY = -(svgY - svgViewBox.h / 2) * zoom + sizes.height / 2

  panZoomInstance.pan({ x: targetPanX, y: targetPanY })
}
```

### 3.4 模板

在 `.forest-container` 内部末尾，添加小地图：

```html
<div v-if="store.svgContent && panZoomInstance" class="forest-minimap"
     :style="{ width: minimapSize.w + 'px', height: minimapSize.h + 'px' }"
     @mousedown.stop
     @click.stop="onMinimapClick">
  <!-- 克隆的 SVG -->
  <div class="forest-minimap-svg" v-html="store.svgContent" />
  <!-- 视口矩形 -->
  <div v-if="minimapViewport" class="forest-minimap-viewport"
       :style="{
         left: minimapViewport.x + 'px',
         top: minimapViewport.y + 'px',
         width: minimapViewport.w + 'px',
         height: minimapViewport.h + 'px',
       }" />
</div>
```

`@mousedown.stop` 防止拖拽小地图时触发主视图的 pan。

### 3.5 新增 state

```typescript
const minimapSize = ref({ w: 180, h: 120 })
let svgViewBox: { w: number; h: number } | null = null  // 在 initPanZoom 时存储
const minimapViewport = ref<{ x: number; y: number; w: number; h: number } | null>(null)
```

### 3.6 svg-pan-zoom 回调中同步视口

`initPanZoom` 中增加 `onPan` 和 `onZoom` 回调：

```typescript
function initPanZoom() {
  // ...
  const vb = parseSvgViewBox(store.svgContent)
  svgViewBox = vb

  panZoomInstance = svgPanZoom(svgEl, {
    // ... 现有配置 ...
    onPan: () => { minimapViewport.value = computeMinimapViewport() },
    onZoom: () => { minimapViewport.value = computeMinimapViewport() },
  })
  
  // 初始计算一次
  minimapViewport.value = computeMinimapViewport()
}
```

### 3.7 CSS

```css
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
  box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}

.forest-minimap-svg {
  width: 100%;
  height: 100%;
  pointer-events: none; /* 点击穿透到父容器 */
}

.forest-minimap-svg :deep(svg) {
  width: 100%;
  height: 100%;
  display: block;
}

.forest-minimap-viewport {
  position: absolute;
  border: 1.5px solid #3b82f6;
  background: rgba(59, 130, 246, 0.12);
  pointer-events: none;
  border-radius: 2px;
}
```

---

## 四、改动范围

| 改动 | 位置 |
|------|------|
| 新增工具栏行 + 重置按钮 | template，`.forest-container` 上方 |
| 新增小地图 DOM | template，`.forest-container` 内部末尾 |
| 新增 `minimapSize`、`svgViewBox`、`minimapViewport` ref | script |
| 新增 `onResetView` | script |
| 新增 `computeMinimapViewport` | script |
| 新增 `onMinimapClick` | script |
| 修改 `initPanZoom`：存储 svgViewBox + 增加 onPan/onZoom 回调 | script |
| 新增 `.forest-toolbar`、`.forest-minimap*` CSS | style |

**仅修改 `ForestViewer.vue`，不涉及后端。**

## 五、不确定点（待验证）

1. **视口矩形位置精度**：`computeMinimapViewport` 公式基于 `getPan()` / `getZoom()` 语义推导。sv-pan-zoom 的 pan 值语义在不同版本可能微调，如果视口框与实际看到的不完全对齐，可调整公式
2. **小地图点击跳转精度**：同上，公式可能需要微调
3. **小地图 SVG 渲染性能**：克隆整个森林 SVG 到 180×120 容器，节点多时可能占内存。如卡顿，改用矩形表示法（大方框=整体布局，小方框=视口）

## 补充变更：SVG 克隆 → 矩形表示

原始设计使用 `v-html` 克隆完整 SVG 到小地图容器（180×120px），在节点数多（数百个）的森林图中导致渲染性能问题。

**变更**：改为两个 `<div>` 矩形——全图区域矩形（`.forest-minimap-area`，浅灰底+边框）表示 SVG 整体范围，视口矩形（`.forest-minimap-viewport`，蓝色半透明）表示当前可见区域。

`computeMinimapViewport()` 公式和 `onMinimapClick()` 点击跳转逻辑不变。

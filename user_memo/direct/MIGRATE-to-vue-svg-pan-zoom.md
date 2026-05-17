# 迁移: 手写小地图 → vue-svg-pan-zoom 内置 thumbnail

> 状态: aligned
> 关联: TASK2605-0x8 森林可视修复
> 目标文件: `ForestViewer.vue`（重写）、`package.json`（新增依赖）

---

## 一、迁移动因

当前手写的小地图方案需要维护：
- `minimapSize` computed（动态计算尺寸、保持容器长宽比）
- `computeMinimapViewport()`（视口映射公式）
- `onMinimapClick()`（坐标换算）
- 模板中 minimap 的 DOM 结构 + CSS

`vue-svg-pan-zoom` 库原生提供 `#thumbnail` 插槽，上述全部由库内部处理，零手写公式。

---

## 二、新增依赖

```bash
cd frontend && npm install vue-svg-pan-zoom
```

该库依赖 `svg-pan-zoom@3.6.0`（当前项目使用 `3.6.2`，semver 兼容）。现有 `svg-pan-zoom` 的 import 可移除（由 `vue-svg-pan-zoom` 内部引用）。

---

## 三、删除清单

以下从 `ForestViewer.vue` 全部删除：

### state (ref / computed / let)
- `minimapSize` computed
- `containerSize` ref
- `minimapViewport` ref
- `panZoomReady` ref
- `panZoomInstance` let
- `svgViewBox` let（保留 `parseSvgViewBox` 函数用于计算 `fitZoom`）

### 函数
- `initPanZoom()`
- `destroyPanZoom()`
- `computeMinimapViewport()`
- `onMinimapClick()`

### 生命周期
- `watch(() => store.svgContent, ...)` 中的 `initPanZoom()` / `destroyPanZoom()` 调用
- `onMounted` 中的 ResizeObserver（由库内部处理或保留简化版）
- `onUnmounted` 中的 `destroyPanZoom()`

### 模板
- `.forest-minimap` div 及其子元素（整个小地图块）
- `.forest-container` 上的 `ref="containerRef"` 和 `v-html="store.svgContent"`

### CSS
- `.forest-minimap` 样式块
- `.forest-minimap-viewport` 样式块
- `.forest-container :deep(svg)` 样式（由库管理 SVG 尺寸）

### import
- 删除 `import svgPanZoom from 'svg-pan-zoom'`

---

## 四、新增清单

### 4a. import

```typescript
import SvgPanZoom from 'vue-svg-pan-zoom'
```

### 4b. 新增 state

```typescript
// svg-pan-zoom 实例引用（通过 @created 事件获取）
let panZoomInstance: SvgPanZoom.Instance | null = null

// 当前计算的 fitZoom，用于 minZoom prop
const currentFitZoom = ref(0.5)

// 视图内容标记（用于 didPan 守卫）
const didPan = ref(false)
```

`didPan` 和 `selectedTreeRoot` 保留不变。

### 4c. 新增函数

#### `onPanZoomCreated(instance)` — 接收 svg-pan-zoom 实例

```typescript
function onPanZoomCreated(instance: SvgPanZoom.Instance) {
  panZoomInstance = instance
}
```

#### `onResetView()` — 修改实现

```typescript
function onResetView() {
  if (!panZoomInstance) return
  panZoomInstance.fit()
  panZoomInstance.center()
  didPan.value = false
}
```

#### `computeAndSetFitZoom()` — 从 SVG 内容计算 fitZoom

在 `watch(() => store.svgContent)` 中，SVG 内容就绪后：
```typescript
const vb = parseSvgViewBox(newVal)
if (vb && containerWrapperRef.value) {
  const cw = containerWrapperRef.value.clientWidth
  const ch = containerWrapperRef.value.clientHeight
  if (cw > 0 && ch > 0) {
    currentFitZoom.value = Math.min(cw / vb.w, ch / vb.h)
  }
}
```

### 4d. 模板 — 核心结构

```html
<template>
  <el-card shadow="never" v-loading="store.isRunning">
    <!-- 空状态（不变） -->
    <div v-if="!store.svgContent && !store.isRunning" style="text-align: center; padding: 40px; color: #999;">
      {{ props.emptyMessage || STR.forestViewer.emptyFallback }}
    </div>

    <!-- 主内容 -->
    <div v-if="store.svgContent" class="forest-wrapper">
      <!-- 状态浮层（不变） -->
      <div v-if="store.trees.length > 0" class="forest-status-overlay" @click="toggleStatusBar">
        📋 {{ store.errors.length + store.warnings.length }}
        <span v-if="showStatusDetail">
          &nbsp;{{ store.trees.length }} 树 {{ store.finalMapping.length }} 映射 {{ store.warnings.length }} 警告 {{ store.errors.length }} 错误
        </span>
      </div>

      <!-- 容器（事件委托在此层） -->
      <div
        ref="containerWrapperRef"
        class="forest-container"
        @mouseover="onMouseOver"
        @mouseout="onMouseOut"
        @click="onNodeClick"
      >
        <SvgPanZoom
          v-if="store.svgContent"
          style="width: 100%; height: 100%;"
          :fit="true"
          :center="true"
          :minZoom="currentFitZoom"
          :maxZoom="500"
          :zoomScaleSensitivity="0.5"
          :controlIconsEnabled="false"
          :dblClickZoomEnabled="true"
          :mouseWheelZoomEnabled="true"
          @beforePan="() => didPan = true"
          @created="onPanZoomCreated"
        >
          <template #default>
            <div v-html="store.svgContent" />
          </template>
          <template #thumbnail>
            <div v-html="store.svgContent" />
          </template>
        </SvgPanZoom>
      </div>
    </div>
  </el-card>
</template>
```

关键点：
- 事件委托（mouseover/mouseout/click）放在 `.forest-container` 包装层，事件从 SVG 元素冒泡上来
- `@beforePan` 通过箭头函数保持 `didPan` 守卫
- `@created` 获取实例引用用于 `onResetView`
- `#default` 和 `#thumbnail` 插槽均通过 `v-html` 渲染 SVG 字符串
- `v-if="store.svgContent"` 确保 SVG 内容就绪后才挂载 `SvgPanZoom`

### 4e. script — watch 简化

`watch(() => store.svgContent)` 改为：

```typescript
watch(() => store.svgContent, async (newVal) => {
  if (!newVal) {
    panZoomInstance = null
    return
  }
  // 等待 DOM 渲染后计算 fitZoom
  await nextTick()
  const vb = parseSvgViewBox(newVal)
  if (vb && containerWrapperRef.value) {
    const cw = containerWrapperRef.value.clientWidth
    const ch = containerWrapperRef.value.clientHeight
    if (cw > 0 && ch > 0) {
      currentFitZoom.value = Math.min(cw / vb.w, ch / vb.h)
    }
  }
}, { immediate: true })
```

### 4f. 生命周期 — 简化

`onMounted` 中只保留必要的初始化。ResizeObserver 保留但不操作 `panZoomInstance`（`SvgPanZoom` 组件已挂载，容器尺寸变时由组件的 `v-if` 重新挂载机制处理，或保留 ResizeObserver 调用 `panZoomInstance?.resize()` + `panZoomInstance?.fit()`）：

```typescript
let ro: ResizeObserver | null = null

onMounted(() => {
  if (containerWrapperRef.value) {
    ro = new ResizeObserver(() => {
      if (panZoomInstance) {
        panZoomInstance.resize()
        panZoomInstance.fit()
      }
      // fitZoom 也需重新计算
      if (store.svgContent) {
        const vb = parseSvgViewBox(store.svgContent)
        if (vb && containerWrapperRef.value) {
          const cw = containerWrapperRef.value.clientWidth
          const ch = containerWrapperRef.value.clientHeight
          if (cw > 0 && ch > 0) {
            currentFitZoom.value = Math.min(cw / vb.w, ch / vb.h)
          }
        }
      }
    })
    ro.observe(containerWrapperRef.value)
  }
})

onUnmounted(() => {
  ro?.disconnect()
  panZoomInstance = null
})
```

注意：`minZoom` 在 `SvgPanZoom` 挂载后无法动态更新。若容器尺寸显著变化导致 `fitZoom` 改变，`@beforePan` 守卫不能动态调整 `minZoom`。折中方案：接受初始 `minZoom` 为挂载时的值，resize 后用户若 zoom out 到旧 minZoom 之下（新 minZoom 之上），视觉上无异常（只是不能进一步 zoom out 到新 contain 状态）。优先保证初始状态正确。

### 4g. 保留不变

| 项目 | 原因 |
|------|------|
| `onMouseOver` / `onMouseOut` | 基于 DOM 属性 `[data-tree-node]` 的高亮逻辑 |
| `onNodeClick` | 含 `didPan` 守卫的选枝逻辑 |
| `clearSelection`、`selectedTreeRoot` | 分支决策状态 |
| `defineExpose({ resetView: onResetView })` | 暴露给父组件调用 |
| `showStatusDetail` / `toggleStatusBar` | 状态栏展开/收起 |
| `parseSvgViewBox()` | 用于计算 `currentFitZoom` |
| CSS: `:deep([data-tree-node])` 规则 | SVG 节点样式 |

### 4h. CSS 调整

```css
/* 删除以下块 */
.forest-container :deep(svg) { ... }  /* 删除，库管理 SVG 尺寸 */
.forest-minimap { ... }              /* 删除 */
.forest-minimap-viewport { ... }     /* 删除 */

/* 保留 */
.forest-wrapper { ... }
.forest-container { ... }  /* 边框/圆角/overflow/背景等保留 */
.forest-status-overlay { ... }
:deep([data-tree-node]) { ... }
:deep([data-tree-node].selected) { ... }
.forest-toolbar { ... }    /* 注：当前模板中未使用，可保留或清理 */
```

`el-card` / `el-card__body` 的 flex 布局保留（用于弹性链条）。

---

## 五、改动范围

| 文件 | 改动类型 |
|------|---------|
| `frontend/package.json` | 新增 `vue-svg-pan-zoom` 依赖 |
| `frontend/src/components/ForestViewer.vue` | 模板、脚本、CSS 全面改写 |

**不改动**：`ForestPage.vue`、后端代码、store、router、测试文件（需同步调整测试中对 `containerRef` 等已删除 API 的引用）。

---

## 六、验证要点

1. SVG 首次加载 → 正确 fit，无裁切/溢出
2. 滚轮缩放 → 以鼠标位置为中心
3. 拖拽平移 → 流畅跟随
4. 缩放到 contain → 不能再 zoom out
5. 小地图 → 自动显示视口框，缩放/平移时实时跟随
6. 点击小地图 → 视口跳转
7. hover 节点 → 关联高亮
8. click pending → 选枝模式
9. 拖拽后 click → 不触发选枝
10. 窗口 resize → SVG 重新适配，小地图视口框更新
11. 切换显示模式 → 新 SVG 正确加载
12. TypeScript 类型检查通过
13. 现有测试通过

---

## 七、风险提示

1. **v-html 在 SvgPanZoom 插槽中**：`SvgPanZoom` 通过 `querySelector('svg')` 查找 SVG 元素。若 `v-html` 渲染的 `<div>` 中包含 `<svg>`，`querySelector` 应能找到。若不能，改用 `DOMParser` 解析 SVG 字符串创建真实 DOM 后插入。
2. **缩略图 SVG ID 冲突**：同一 SVG 字符串在主视图和缩略图中各渲染一次，若 SVG 内部使用 ID 引用（如渐变），可能冲突。库的 thumbnail 实现通常会处理此问题；若有异常，可对缩略图副本做 ID 去重处理。
3. **minZoom 动态更新限制**：`SvgPanZoom` 的 prop `minZoom` 只在挂载时生效，resize 后不会更新。优先保证初始状态正确，resize 场景作为已知限制。

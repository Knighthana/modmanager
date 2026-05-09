# TODO-15 Step 1: Forest SVG 自适应视窗宽度缩放

> 状态: 设计完成，待实现
> 关联: `work_memo/states.md` TODO-15
> 目标文件: `frontend/src/components/ForestViewer.vue`

---

## 一、问题描述

当前 `ForestViewer.vue` 渲染 SVG 时，初始缩放比例固定为 `scale=1`，不考虑容器宽度。当容器较窄时 SVG 会溢出（需手动缩小），当容器较宽时 SVG 偏小（需手动放大）。每次切换/刷新 SVG 均回到 `scale=1`，体验不佳。

## 二、需求

- SVG 首次加载时自动缩放至恰好填满容器宽度（`fitScale = containerWidth / svgNaturalWidth`）
- 容器宽度变化（窗口缩放、侧栏折叠等）时 SVG 自动重新适配
- 用户仍可手动滚轮缩放（缩放范围 0.1× ~ 5×），手动缩放后不再被自动 resize 覆盖
- 适配后 SVG 在容器内垂直居中

## 三、不改动范围

- **不修改 Python 后端** `forest_visual.py` —— Graphviz 生成的 SVG 保持不变
- **不修改** `ForestPage.vue`、`forest.ts` store
- **不添加** zoom 按钮 / reset 控件（第二步"视窗功能增强"再做）

## 四、实现方案

### 全部改动集中在 `ForestViewer.vue`

#### 4.1 新增状态

```typescript
// 容器实际宽度（px），由 ResizeObserver 驱动
const containerWidth = ref(0)

// 用户是否已手动缩放（干预自动 fit）
const userAdjustedScale = ref(false)

// 上次自动 fit 时计算出的 fitScale（用于 resize 时判断是否需要更新）
const lastAutoFitScale = ref(1)
```

#### 4.2 获取 SVG 自然宽度

在 `watch(store.svgContent)` 回调中，`await nextTick()` 后通过 DOM 查询：

```typescript
function getSvgNaturalWidth(): number {
  const svgEl = containerRef.value?.querySelector('svg')
  if (!svgEl) return 0
  // 优先使用 getBoundingClientRect（反映实际渲染尺寸）
  const rect = svgEl.getBoundingClientRect()
  if (rect.width > 0) return rect.width
  // 回退：解析 viewBox（Graphviz SVG 一定有 viewBox）
  const vb = svgEl.getAttribute('viewBox')
  if (vb) {
    const parts = vb.split(/\s+/)
    if (parts.length === 4) return parseFloat(parts[2])
  }
  return 0
}
```

#### 4.3 自适应缩放函数

```typescript
function fitToContainer(): boolean {
  if (!containerRef.value) return false
  const cw = containerRef.value.clientWidth
  if (cw <= 0) return false

  const svgW = getSvgNaturalWidth()
  if (svgW <= 0) return false

  const rawScale = cw / svgW
  const clamped = Math.max(0.1, Math.min(5, rawScale))
  
  scale.value = clamped
  lastAutoFitScale.value = clamped

  // 垂直居中
  const svgH = (containerRef.value.querySelector('svg')?.getBoundingClientRect().height ?? 0)
  const containerH = containerRef.value.clientHeight
  if (svgH > 0 && containerH > 0) {
    const scaledSvgH = svgH * clamped
    const vertOffset = (containerH - scaledSvgH) / 2 / clamped
    offset.value = { x: 0, y: Math.max(0, vertOffset) }
  } else {
    offset.value = { x: 0, y: 0 }
  }
  
  userAdjustedScale.value = false
  return true
}
```

#### 4.4 ResizeObserver

```typescript
let ro: ResizeObserver | null = null

onMounted(() => {
  if (containerRef.value) {
    ro = new ResizeObserver(() => {
      // 仅当用户未曾手动缩放时自动 fit
      if (!userAdjustedScale.value) {
        fitToContainer()
      }
    })
    ro.observe(containerRef.value)
  }
})

onUnmounted(() => {
  ro?.disconnect()
})
```

#### 4.5 SVG 内容变化时触发 fit

```typescript
watch(() => store.svgContent, async (newVal) => {
  if (!newVal) return
  await nextTick()
  fitToContainer()
})
```

#### 4.6 手动缩放时标记

修改现有 `onWheel` 函数，在滚轮事件中设置 `userAdjustedScale = true`：

```typescript
function onWheel(e: WheelEvent) {
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  const newScale = scale.value * delta
  if (newScale < 0.1 || newScale > 5) return
  scale.value = newScale
  userAdjustedScale.value = true  // ← 新增
}
```

### 4.7 缩放动画处理

现有 `.forest-svg { transition: transform 0.05s ease; }` 会在 auto-fit 时产生微小动画。auto-fit 期间可暂时禁用 transition，fit 完成后恢复。但 0.05s 很短，实际体验影响不大，**本次不做处理**。如需优化可在第二步统一改进。

## 五、边界情况

| 场景 | 行为 |
|------|------|
| SVG 尚未加载（svgContent 为空） | 什么都不做，ResizeObserver 也跳过 |
| 容器宽度为 0（display: none） | 跳过 fit |
| SVG 无 viewBox（极小概率） | 回退到 getBoundingClientRect；若仍为 0，scale 保持 1 |
| SVG 极窄（<10px viewBox） | clamp 到 scale=5 上限 |
| SVG 极宽（>10000px） | clamp 到 scale=0.1 下限 |
| 用户手动缩小到 0.5× 后 resize 窗口 | 保持 0.5×（userAdjustedScale=true） |

## 六、测试要点

1. 打开 Forest 页面，计算映射 → SVG 应自动填满卡片宽度
2. 缩放浏览器窗口 → SVG 跟随缩放
3. 滚轮缩放后 → 再缩放窗口，SVG 保持用户选择的缩放比例
4. 切换"全部/仅分枝" → 新 SVG 应重新自动 fit
5. 极窄窗口（<400px）→ scale 不低于 0.1

## 七、实现指令

文件: `frontend/src/components/ForestViewer.vue`

改动点:
1. 在 `<script setup>` 中新增 `containerWidth`、`userAdjustedScale`、`lastAutoFitScale` 三个 ref
2. 新增 `getSvgNaturalWidth()` 函数
3. 新增 `fitToContainer()` 函数
4. 新增 `watch(() => store.svgContent, ...)` 监听 SVG 变化触发 fit
5. 在 `onMounted` 中创建 ResizeObserver，`onUnmounted` 中断开
6. 在 `onWheel` 中新增 `userAdjustedScale.value = true`
7. 添加必要的 import：`watch`、`nextTick`、`onMounted`、`onUnmounted`

不新建文件，不修改其他文件。

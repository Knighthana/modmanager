# 森林可视修复 — TASK2605-0x8

> 状态: aligned
> 关联: 森林可视体验改进
> 目标文件: `ForestPage.vue`、`ForestViewer.vue`

---

## 设计原则

- **零硬编码魔数**：所有高度/间距通过 CSS flex 链条由浏览器自动计算。
- **最小倍率 = contain**：`minZoom` 等于 `fitZoom`，用户缩放到 contain 状态即为下限。
- **小地图真实反映视口**：外框反映容器长宽比，内框反映当前 zoom/pan 下的视口位置与占比。

---

## 一、弹性高度链条（修复问题1：初次渲染尺寸偏差）

### 1a. `ForestPage.vue` 模板

在第34行，将 `<ForestViewer>` 外包一层：

```html
<div class="forest-viewer-wrap">
  <ForestViewer ref="forestViewerRef" :empty-message="emptyMessage" />
</div>
```

### 1b. `ForestPage.vue` 样式

在 `<style scoped>` 尾部追加：

```css
.forest-page {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.forest-viewer-wrap {
  flex: 1;
  min-height: 0;
}
```

> `height: 100%` 依赖 LayoutShell 中 `el-main` 已有的定高（`100vh` 经 flex stretch 传递），无需额外计算。

### 1c. `ForestViewer.vue` 模板

第15行删除 `:style="{ height: containerHeight + 'px' }"`：

```diff
-      :style="{ height: containerHeight + 'px' }"
```

### 1d. `ForestViewer.vue` 脚本 — 删除

- 删除第60行：`const containerHeight = ref(window.innerHeight - 120)`
- 删除第236-237行的 window resize 事件监听（保留 ResizeObserver 注册）：

```diff
-  const updateHeight = () => { containerHeight.value = window.innerHeight - 180 }
-  window.addEventListener('resize', updateHeight)
```

### 1e. `ForestViewer.vue` 脚本 — 新增 containerSize

在 `minimapSize` 附近新增：

```typescript
const containerSize = ref({ w: 800, h: 600 })
```

在 `initPanZoom()` 中读容器尺寸后写入（第98行后追加）：

```typescript
containerSize.value = { w: containerW, h: containerH }
```

修改 ResizeObserver 回调（第240行），在开头追加尺寸更新：

```typescript
ro = new ResizeObserver(() => {
  if (containerRef.value) {
    containerSize.value = {
      w: containerRef.value.clientWidth,
      h: containerRef.value.clientHeight,
    }
  }
  if (panZoomInstance) {
    panZoomInstance.resize()
    panZoomInstance.fit()
    minimapViewport.value = computeMinimapViewport()
  }
})
```

### 1f. `ForestViewer.vue` 样式 — flex 链条

```css
/* 根节点 el-card 填充父容器 */
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

.forest-wrapper {
  position: relative;  /* 原有，保留 */
  flex: 1;
  min-height: 0;
}

.forest-container {
  width: 100%;
  height: 100%;       /* 原为 100px */
  /* border / border-radius / overflow / cursor / position / background 不变 */
}

.forest-minimap-area {
  position: absolute;
  /* 删除 inset: 2px; 改由动态 :style 控制 */
  border: 1px solid #94a3b8;
  background: #f8fafc;
  border-radius: 2px;
  pointer-events: none;
}
```

---

## 二、minZoom 确认（修复问题2：最小倍率）

`minZoom = fitZoom` 已满足"缩到 contain 后不允许继续缩小"。第104行 **不动**。

修复一确保 `fitZoom` 基于正确的容器尺寸计算，从而消除误差传导。

`zoomScaleSensitivity: 0.5` 保持不变。

---

## 三、小地图重构（修复问题3：矩形表示与视口映射）

### 3a. 新增 computed

```typescript
const minimapArea = computed(() => {
  const mmW = minimapSize.value.w   // 180
  const mmH = minimapSize.value.h   // 120
  const cw = containerSize.value.w
  const ch = containerSize.value.h
  if (cw <= 0 || ch <= 0) {
    return { x: 0, y: 0, w: mmW, h: mmH }
  }
  const containerAspect = cw / ch
  const margin = 4
  const availW = mmW - margin
  const availH = mmH - margin

  let areaW: number, areaH: number
  if (containerAspect > availW / availH) {
    areaW = availW
    areaH = availW / containerAspect
  } else {
    areaH = availH
    areaW = availH * containerAspect
  }
  return {
    x: (mmW - areaW) / 2,
    y: (mmH - areaH) / 2,
    w: areaW,
    h: areaH,
  }
})
```

### 3b. 重写 `computeMinimapViewport()`

```typescript
function computeMinimapViewport(): { x: number; y: number; w: number; h: number } | null {
  if (!panZoomInstance || !svgViewBox || !containerRef.value) return null

  const zoom = panZoomInstance.getZoom()
  const pan  = panZoomInstance.getPan()
  const cw = containerRef.value.clientWidth
  const ch = containerRef.value.clientHeight
  const vbW = svgViewBox.w
  const vbH = svgViewBox.h

  const fitZoom = Math.min(cw / vbW, ch / vbH)
  const totalW = cw / fitZoom   // contain 时可见 SVG 空间总宽度
  const totalH = ch / fitZoom   // contain 时可见 SVG 空间总高度

  // 内框占外框的比例 (zoom 越大内框越小，fitZoom 时 fracSize = 1)
  const fracSize = fitZoom / zoom

  // pan 导致的中心偏移 (SVG 坐标)
  const offsetCenterX = pan.x / zoom
  const offsetCenterY = pan.y / zoom

  // 视口中心在 total 空间中的分数位置 (0.5 = 居中)
  const fracX = 0.5 - offsetCenterX / totalW
  const fracY = 0.5 - offsetCenterY / totalH

  const outerW = minimapArea.value.w
  const outerH = minimapArea.value.h
  const outerX = minimapArea.value.x
  const outerY = minimapArea.value.y

  const innerW = outerW * fracSize
  const innerH = outerH * fracSize

  let innerX = outerX + fracX * outerW - innerW / 2
  let innerY = outerY + fracY * outerH - innerH / 2

  // clamp 到外框范围内
  innerX = Math.max(outerX, Math.min(outerX + outerW - innerW, innerX))
  innerY = Math.max(outerY, Math.min(outerY + outerH - innerH, innerY))

  return { x: innerX, y: innerY, w: innerW, h: innerH }
}
```

### 3c. 重写 `onMinimapClick()`

```typescript
function onMinimapClick(e: MouseEvent) {
  if (!panZoomInstance || !svgViewBox || !containerRef.value) return

  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top

  // 点击位置在外框中的分数坐标
  const fx = (mx - minimapArea.value.x) / minimapArea.value.w
  const fy = (my - minimapArea.value.y) / minimapArea.value.h
  const cfx = Math.max(0, Math.min(1, fx))
  const cfy = Math.max(0, Math.min(1, fy))

  const cw = containerRef.value.clientWidth
  const ch = containerRef.value.clientHeight
  const vbW = svgViewBox.w
  const vbH = svgViewBox.h

  const fitZoom = Math.min(cw / vbW, ch / vbH)
  const totalW = cw / fitZoom
  const totalH = ch / fitZoom
  const totalLeft = vbW / 2 - totalW / 2
  const totalTop  = vbH / 2 - totalH / 2

  const svgX = totalLeft + cfx * totalW
  const svgY = totalTop  + cfy * totalH

  const zoom = panZoomInstance.getZoom()
  const targetPanX = (vbW / 2 - svgX) * zoom
  const targetPanY = (vbH / 2 - svgY) * zoom

  panZoomInstance.pan({ x: targetPanX, y: targetPanY })
}
```

### 3d. 模板改动

第31行，`forest-minimap-area` 增加动态 `:style`：

```diff
-        <div class="forest-minimap-area" />
+        <div class="forest-minimap-area"
+             :style="{
+               left: minimapArea.x + 'px',
+               top: minimapArea.y + 'px',
+               width: minimapArea.w + 'px',
+               height: minimapArea.h + 'px',
+             }" />
```

内框 `forest-minimap-viewport`（第32-38行）的 `:style` 保持不变。

---

## 四、改动汇总

| 文件 | 改动 | 区域 |
|------|------|------|
| ForestPage.vue | 模板: 包裹 ForestViewer | 第34行 |
| ForestPage.vue | CSS: `.forest-page` + `.forest-viewer-wrap` | `<style scoped>` 末尾 |
| ForestViewer.vue | 模板: 删除 `:style` 高度绑定 | 第15行 |
| ForestViewer.vue | 模板: area 动态 style | 第31行 |
| ForestViewer.vue | 脚本: 删除 `containerHeight` | 第60行 |
| ForestViewer.vue | 脚本: 删除 window resize 监听 | 第236-237行 |
| ForestViewer.vue | 脚本: 新增 `containerSize` ref | minimapSize 附近 |
| ForestViewer.vue | 脚本: 新增 `minimapArea` computed | 同上 |
| ForestViewer.vue | 脚本: `initPanZoom` 写入 containerSize | 第98行后 |
| ForestViewer.vue | 脚本: ResizeObserver 写入 containerSize | 第240行 |
| ForestViewer.vue | 脚本: 重写 `computeMinimapViewport` | 第172-199行 |
| ForestViewer.vue | 脚本: 重写 `onMinimapClick` | 第202-219行 |
| ForestViewer.vue | CSS: el-card / body flex | `<style scoped>` 追加 |
| ForestViewer.vue | CSS: `.forest-wrapper` flex | 已有块修改 |
| ForestViewer.vue | CSS: `.forest-container` height 100% | 已有块修改 |
| ForestViewer.vue | CSS: `.forest-minimap-area` 删 inset | 已有块修改 |

**不改动**：`minZoom`、`zoomScaleSensitivity`、后端代码、store、路由。

## 五、验证要点

1. 首次进入森林页 → SVG 正确适配容器，不裁切不溢出
2. 调浏览器宽度/高度 → SVG 自动 re-fit，无明显偏差
3. 滚轮缩小到 contain → 不能再缩小，图片始终可见
4. 小地图外框 → 长宽比与 SVG 容器一致
5. 小地图内框 → 缩放时内框大小改变（zoom↑内框↓），平移时内框位置跟随
6. 内框最大 = 外框（contain 时）
7. 点击小地图 → 视口正确跳转
8. 手动缩放后 resize → 视图不被强制重置

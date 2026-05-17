# 前端集成约束

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 约束前端第三方库的调用方式与参数语义，减少实现偏差与回归风险。

## 适用范围
- 前端组件与交互层中对第三方库的直接调用。
- 当前首个约束主题: svg-pan-zoom 在森林图中的缩放边界配置。

## svg-pan-zoom 调用约定（ForestViewer）
1. 当需求为“最小状态下恰好 fit 容器”时，固定使用 minZoom = 1。
2. minZoom 必须通过语义常量传值，例如 MIN_ZOOM_RELATIVE_TO_FIT = 1。
3. 诊断变量允许存在，但变量名必须显式包含 diagnostic，且仅用于日志。
4. 诊断变量不得直接或间接传入 minZoom / maxZoom。
5. maxZoom 按业务需求独立配置，不与诊断变量耦合。

## 推荐配置模板
```ts
const MIN_ZOOM_RELATIVE_TO_FIT = 1
const originalViewportZoomDiagnostic = vb ? Math.min(cw / vb.w, ch / vb.h) : 0.5

panZoomInstance = svgPanZoom(svgEl, {
  fit: true,
  center: true,
  minZoom: MIN_ZOOM_RELATIVE_TO_FIT,
  maxZoom: 80,
})
```

## 命名与注释要求
- 语义常量: 使用 MIN_ / MAX_ 前缀表达边界约束。
- 诊断变量: 使用 Diagnostic 后缀并附带“禁止用于配置”的注释。
- 关键传参处: 添加注释指向本文件，便于 code review 快速核对。

## 验收与回归
1. 单测必须断言 svg-pan-zoom 初始化参数中的 minZoom === 1。
2. 手工验收必须覆盖:
   - 初始加载处于 fit 状态
   - zoom out 到下限后停止
   - zoom in 与 reset 行为正常

## 背景索引
- 机制解释与源码路径: ../repo_bkgd/SVG_PAN_ZOOM.md

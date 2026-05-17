# SVG Pan Zoom 背景说明

> Status: active
> Authority: reference-only
> Read-Tier: on-demand
> Purpose: 记录 svg-pan-zoom 的缩放基准机制、参数换算与历史误用案例，供问题追溯与知识传递。

## 背景
在森林图交互中，初始化通常使用 fit 模式以保证大图可见。
当团队成员把容器与 viewBox 比值得到的绝对缩放值直接传入 minZoom 时，可能出现最小缩放被进一步平方缩小的问题。

## 机制要点
1. fit 基准会在初始化时计算并写入 originalState.zoom。
2. minZoom / maxZoom 是相对原始基准的系数，不是绝对缩放值。
3. 缩放边界在运行时通过 minZoom * originalState.zoom 参与计算。

## 代码定位（svg-pan-zoom@3.6.2）
- 初始化写入 fit 基准: frontend/node_modules/svg-pan-zoom/src/shadow-viewport.js
- 缩放边界乘以 originalState.zoom: frontend/node_modules/svg-pan-zoom/src/svg-pan-zoom.js
- 文档说明“Zoom is relative to initial SVG internal zoom level”: frontend/node_modules/svg-pan-zoom/README.md

## 历史误用案例（摘要）
- 场景: fit: true，图像远大于容器。
- 误用: 计算得到 fitZoom 后直接赋给 minZoom。
- 结果: 最小缩放下限过低，用户可继续 zoom out 到非常小。

## 当前结论
- 当需求是“最小状态下恰好 fit 容器”，应使用 minZoom = 1（相对 fit 基准）。
- 诊断型缩放值可保留用于日志排障，但不得作为 minZoom 传参。

## 关联规范
- 约束规范（怎么做）: ../repo_memo/FRONTEND_INTEGRATION_CONSTRAINTS.md

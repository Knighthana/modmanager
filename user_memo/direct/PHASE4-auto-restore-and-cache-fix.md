# Phase 4 — 自动恢复与缓存行为基线（已落地）

> Status: aligned
> Authority: user-guidance
> Purpose: 固化自动恢复与扫描缓存行为，避免回归

---

## 一、目标

本阶段目标是提升刷新后可恢复性，同时防止 manual 扫描被旧缓存误命中。

当前生效原则：
1. 自动恢复走 workspace 单键持久化模型。
2. manual 与 auto 模式语义必须可区分。
3. Forest 页面保持结果消费职责，不承担计算触发职责。

---

## 二、当前基线

1. datasource 页面可按当前数据库上下文恢复展示。
2. advanced 页面 tab 切换刷新策略已统一。
3. forest 页面读取已计算结果并展示，不越界触发计算。

---

## 三、implement guardrails

1. 不回退到分散 key（如 `results:{db}`）存储模型。
2. 不在 Forest 页面新增 compute/run 触发流程。
3. manual 扫描路径必须优先遵循用户输入语义，不被旧缓存短路。
4. 自动恢复失败时允许降级，不应阻断页面主流程。

---

## 四、增量验证清单

1. 刷新后 datasource、advanced、forest 状态一致。
2. 切换数据库名称后，恢复状态跟随数据库上下文。
3. 前端测试与构建均通过。

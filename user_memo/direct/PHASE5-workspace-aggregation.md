# Phase 5 — 契约对齐基线（已落地）

> Status: aligned
> Authority: user-guidance
> Source: repo_memo 当前冻结契约 + 已落地代码

---

## 一、目标

本文件保留 Phase 5 的核心目标，但不再描述已过时的迁移路径。

当前目标仅有两条：
1. 前端持久化统一到单键 `modmanager:workspace`。
2. compute/run 使用 `aggregated_rule_set` 契约，禁止回退到旧字段。

---

## 二、当前已落地状态

### 2.1 workspace 单键聚合
- 已落地：`lastDatabase`、`perDatabase.decisions/results`、`aggregatedRuleMeta` 在同一 workspace 结构中管理。
- 已落地：workspace 读写入口统一为 persistence 工具，避免多写者。
- 已落地：删除旧的 workspace store 双写入口。

### 2.2 pipeline 请求口径
- 已落地：前端 compute/run 使用 `aggregated_rule_set`。
- 已落地：`managed_entries` 与 `branch_decisions` 按数据库上下文传入。
- 已落地：Forest 页面职责收敛为结果消费，不再作为计算入口。

---

## 三、实施 guardrails（implement 必遵守）

1. 不新增分散 localStorage key（如 decisions:name/results:name 形式）。
2. 不恢复旧字段（`kmm_rule_paths`、`kmm_rules`、`aggregated_rule_path` 作为 compute 主路径字段）。
3. 不重建 workspace API 端点；workspace 仍由前端 localStorage 承担。
4. 新增字段前，先对齐 repo_memo 的字段冻结文档。

---

## 四、后续只做增量检查

如需继续改动，仅做以下检查：
1. `frontend` 测试通过。
2. `frontend` build 通过。
3. 变更后 `DESIGN_GUI_WORKSPACE` 与实现一致。

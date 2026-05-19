# AUDIT-ALIGN — 审计对齐执行清单

> Source: `user_memo/audit_logs/2026-05-14_Architecture-Design-Freeze-and-Cleanup.md`
> Answers: `work_memo/2026-05-14_audit_answers.md`
> 原则：先改权威文档，再改代码

---

## Phase A：文档清理残留（审计 §2.1）

### A1. `DESIGN_STORAGE.md:320`
删除 D4 决策中的"【已废弃】"字样，改为现状描述

### A2. `DESIGN_FOREST_MODEL.md`
删除多处 "forest→trees" 迁移说明。保留代码变更对照表但去掉"迁移"语义——直接写 trees 仿佛从来如此

### A3. `DESIGN_RULE_AGGREGATOR.md:169`
删除 nwname "已废弃 2026-04-30" 标记

### A4. `DESIGN_REST_API.md` 首段
删除 "forest→trees" migration note

---

## Phase B：字段冻结补充（审计 §1.2）

### B1. `TERMS_FIELD_FREEZE.md`
新增 4 个冻结字段：`selectedRulePaths`、`managedEntries`、`branchDecisions`、`lastComputeSummary`，格式按审计报告定义

---

## Phase C：REST_API 状态更新（审计 §1.6-1.7）

### C1. `DESIGN_REST_API.md` header
Status 从 `stable` → `partially-stable`

### C2. 端点分组表
新增表格区分 STABLE 端点和 EVOLVING 端点（per 审计 §1.6-1.7）

---

## Phase D：workspace 结构命名统一（审计 §1.1 + 答复 #1）

### D1. `DESIGN_GUI_WORKSPACE.md`
将所有 snake_case 字段改为审计规定的 camelCase：
- `managed_entries` → `managedEntries`
- `branch_decisions` → `branchDecisions`
- `results` → `lastComputeSummary`
- `aggregatedRuleSet` → 删除（不进 localStorage）
- `aggregatedRuleHash` → 保留
- 新增 `selectedRulePaths`

---

## Phase E：代码对齐

### E1. 文档对齐完成后再改代码
按更新后的文档统一字段命名

---

## 执行顺序
A1 → A2 → A3 → A4 → B1 → C1 → C2 → D1
（代码 E1 在全部文档对齐后执行）

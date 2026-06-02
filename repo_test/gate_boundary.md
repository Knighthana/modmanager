# gate_boundary — gate/preflight 逻辑边界

> Status: active
> Authority: normative
> Read-Tier: task-scoped
> Purpose: 裁定 14 的测试断言 — 验证 `check_backup_gate` 及 gate 逻辑从原语迁移到 Planner
> 依据: `DESIGN_PLANNER.md`、`DESIGN_BACKUP_OPS.md`、`work_memo/2026-06-01_TASK_arch_drift_review.md` 裁定 14

---

## 一、适用范围

gate / preflight 逻辑由 Planner 及附属部件（`preflight.py`）独占：

| 函数 | 原位置 | 目标位置 |
|------|--------|---------|
| `check_backup_gate()` | `backup_ops.py` | `planner_fileops.py` 或 `preflight.py` |
| `run_apply_preflight()` | `preflight.py`（已正确） | 不变 |
| `run_restore_preflight()` | `preflight.py`（已正确） | 不变 |

原语（backup / restore / apply）不持有任何 gate / preflight 逻辑。

---

## 二、黑箱测试断言

### 2.1 原语边界

| # | 断言 | 级别 |
|---|------|:---:|
| T-GT-01 | `from modmgr.backup_ops import check_backup_gate` → `ImportError` | MUST |
| T-GT-02 | `backup_ops.__all__` 不含 `"check_backup_gate"` | MUST |
| T-GT-03 | `backup_ops.py` 中不存在任何名为 `check_*_gate` 的函数 | MUST |
| T-GT-04 | `apply_ops.py` 不 import `backup_ops` 的 gate 函数 | MUST |
| T-GT-05 | `preflight.py` 不 import `backup_ops`（不直接跨原语边界引用） | MUST |

### 2.2 Planner 新职责

| # | 断言 | 级别 |
|---|------|:---:|
| T-GT-06 | `check_backup_gate` 在 `planner_fileops.py` 或 `preflight.py` 中可 import | MUST |
| T-GT-07 | Planner 调用的 `check_backup_gate` 功能与迁移前一致（同一输入 → 同一结果） | MUST |
| T-GT-08 | `plan_fileops()` 输出的 `FileOpsPlan.preflight_manifest` 包含 gate 检查结果 | MUST |

### 2.3 文档一致性

| # | 断言 | 级别 |
|---|------|:---:|
| T-GT-09 | `DESIGN_BACKUP_OPS.md` 不含 gate 逻辑描述 | MUST |
| T-GT-10 | `DESIGN_PLANNER.md` 描述 Planner 的 gate 管理职责 | MUST |

---

## 三、验收标准

- [ ] 全部 T-GT-01 ~ T-GT-10 通过
- [ ] 现有备份流程不受影响（gate 检查结果一致）
- [ ] `preflight.py` 不再跨原语边界 import

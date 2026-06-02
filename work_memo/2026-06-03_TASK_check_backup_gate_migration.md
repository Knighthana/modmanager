# 2026-06-03 — check_backup_gate 迁出原语（裁定 14）

> 依据: `work_memo/2026-06-01_TASK_arch_drift_review.md` 阶段 3.2/3.3/3.5

## 变更内容

### 代码迁移

| 操作 | 源 | 目标 |
|------|:--:|:----:|
| `check_backup_gate()` | `backup_ops.py:336-353` | `planner_fileops.py:22-42` |
| import `check_backup_gate` | `preflight.py:17-19` from `backup_ops` | `preflight.py:31` from `planner_fileops`（lazy import，避免循环依赖） |

### backup_ops.py 更新

- 删除 `check_backup_gate` 函数定义及 Phase 9 注释
- 删除 `"check_backup_gate"` 从 `__all__`
- 更新模块 docstring（移除 Phase 9 条目）
- `inspect_conflict()` 和 `restore_from_backup()` 通过 lazy import 从 `planner_fileops` 获取 `check_backup_gate`

### preflight.py 更新

- 删除 `try/except` 从 `backup_ops` 导入 `check_backup_gate`
- `run_apply_preflight()` 内 lazy import `check_backup_gate` 从 `planner_fileops`

### planner_fileops.py 更新

- 新增 `check_backup_gate()` 函数（含 lazy import for `load_backup_info`/`assert_directory_path`）

### 测试更新

- 新建 `tests/test_gate_boundary.py`: T-GT-01 ~ T-GT-08（8/8 PASS）
- `tests/test_backup_ops.py`: 移除 `check_backup_gate` 从 import；更新 patch 路径

## 验证

- 新测试 8/8 PASS
- 现有测试无新增失败（11 项 pre-existing 失败与本次变更无关）
  - `test_preflight.py`: 11 项失败（函数签名不匹配——调用方传 2 参但函数仅 1 参，pre-existing）

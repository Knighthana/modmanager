# 2026-06-03 — .kmmignore 物理拷贝迁入 Planner（裁定 1 + 13）

> 依据: `work_memo/2026-06-01_TASK_arch_drift_review.md` 阶段 3.1/3.4

## 变更内容

### 代码迁移

| 操作 | 源 | 目标 |
|------|:--:|:----:|
| `_copy_kmmignore_to_backup()` | `orchestrator/__init__.py:328-348` | `planner_fileops.py:186-206` |
| `_copy_kmmignore_from_backup()` | `orchestrator/__init__.py:351-366` | `planner_fileops.py:209-225` |

### orchestrator/__init__.py 更新

- 新增 import: `from .planner_fileops import ..., _copy_kmmignore_to_backup, _copy_kmmignore_from_backup`
- 删除 `import os`（不再使用）
- `_dispatch_fileops()` 中的调用保持不变（函数通过 import 继续可用）
- 删除两个 `_copy_kmmignore_*` 函数定义

### 测试更新

- `test_kmmignore_copy.py`: 导入源从 `modmgr.orchestrator` 改为 `modmgr.orchestrator.planner_fileops`
- 新建 `test_kmmignore_lifecycle.py`: T-KI-01 ~ T-KI-06（黑箱位置测试）+ T-KI-13/T-KI-14（过滤行为验证）

## 验证

- 新测试 8/8 PASS
- 现有 `test_kmmignore_copy.py` 9/9 PASS（原有覆盖率不变）
- 全量测试 536 PASS（12 项 pre-existing 失败与本次变更无关）

# kmmignore_lifecycle — .kmmignore 完整生命周期（Planner 管理）

> Status: active
> Authority: normative
> Read-Tier: task-scoped
> Purpose: 裁定 1 + 13 的测试断言 — 验证 `.kmmignore` 文件过滤和物理拷贝均由 Planner 管理
> 依据: `DESIGN_BACKUP_OPS.md`、`DESIGN_PLANNER.md`、`work_memo/2026-06-01_TASK_arch_drift_review.md` 裁定 1/13
> 替代: `repo_test/kmmignore_copy.md`（旧版，仅覆盖 copy 部分）

---

## 一、适用范围

Planner **全权管理** `.kmmignore` 文件生命周期，原语（backup / restore / apply）不感知：

| 阶段 | 操作 | 归属 |
|------|------|:---:|
| 过滤 | 解析 `.kmmignore`（gitignore 语法），在 `plan_fileops()` 中过滤被忽略的文件 | Planner |
| 备份时拷贝 | `_copy_kmmignore_to_backup()`：从源目录拷贝 `.kmmignore` 到 `backup_dir` | Planner |
| 还原时拷贝 | `_copy_kmmignore_from_backup()`：从 `backup_dir` 拷贝 `.kmmignore` 回源目录 | Planner |

---

## 二、黑箱测试断言

### 2.1 迁移后状态

| # | 断言 | 级别 |
|---|------|:---:|
| T-KI-01 | `orchestrator/__init__.py` 不含 `_copy_kmmignore_to_backup` 函数 | MUST |
| T-KI-02 | `orchestrator/__init__.py` 不含 `_copy_kmmignore_from_backup` 函数 | MUST |
| T-KI-03 | `planner_fileops.py` 含 `_copy_kmmignore_to_backup` 函数 | MUST |
| T-KI-04 | `planner_fileops.py` 含 `_copy_kmmignore_from_backup` 函数 | MUST |
| T-KI-05 | `backup_ops.py` 不 import 任何 `.kmmignore` 相关模块或函数 | MUST |
| T-KI-06 | `restore_ops.py` 不 import 任何 `.kmmignore` 相关模块或函数 | MUST |

### 2.2 .kmmignore 拷贝行为

| # | 断言 | 级别 |
|---|------|:---:|
| T-KI-07 | 源目录根存在 `.kmmignore` → backup 后 `backup_dir` 根存在 `.kmmignore`（内容一致） | MUST |
| T-KI-08 | 源目录子目录存在 `.kmmignore` → backup 后 `backup_dir` 对应子目录存在 `.kmmignore` | MUST |
| T-KI-09 | 源目录无 `.kmmignore` → backup 后 `backup_dir` 无 `.kmmignore`（不报错） | MUST |
| T-KI-10 | `backup_dir` 已存在 `.kmmignore` → restore 后源目录对应位置被还原 `.kmmignore`（覆盖） | MUST |
| T-KI-11 | `backup_dir` 无 `.kmmignore` → restore 后源目录无变化（不报错） | MUST |
| T-KI-12 | `.kmmignore` 拷贝失败（权限不足）→ 记录 warning，不阻断整体流程 | SHOULD |

### 2.3 .kmmignore 过滤行为

| # | 断言 | 级别 |
|---|------|:---:|
| T-KI-13 | `plan_fileops()` 返回的 `FileOpsPlan.entries_by_backup_dir` 不含被 `.kmmignore` 忽略的文件 | MUST |
| T-KI-14 | `plan_fileops()` 输出中的 `ignore_rule_set` 缓存可供原语直接消费 | MUST |

### 2.4 文档一致性

| # | 断言 | 级别 |
|---|------|:---:|
| T-KI-15 | `DESIGN_BACKUP_OPS.md §十三` 描述 Planner 管理 `.kmmignore` 生命周期 | MUST |
| T-KI-16 | `DESIGN_RESTORE_OPS.md §八` 不再描述 restore 原语操作 `.kmmignore` | MUST |
| T-KI-17 | `DESIGN_PLANNER.md` 描述 Planner 的 `.kmmignore` 完整生命周期职责 | MUST |

---

## 三、验收标准

- [ ] 全部 T-KI-01 ~ T-KI-17 通过
- [ ] `orchestrator/__init__.py` 中 `_dispatch_fileops` 不再直接操作 `.kmmignore` 文件
- [ ] 现有备份/还原测试不受影响

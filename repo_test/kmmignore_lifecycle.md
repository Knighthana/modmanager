# kmmignore_lifecycle — .kmmignore 原地规则（Planner 管理）

> Status: active
> Authority: normative
> Read-Tier: task-scoped
> Purpose: 裁定 1 + 13 + 2026-06-03 的测试断言 — 验证 `.kmmignore` 原地读取、过滤、不搬动
> 依据: `DESIGN_BACKUP_OPS.md`、`DESIGN_PLANNER.md`、`PENDING.md` Decision 8（原地规则）
> 替代: `repo_test/kmmignore_copy.md`（旧版，描述已废弃的物理拷贝模型）

---

## 一、适用范围

Planner **全权管理** `.kmmignore` 文件 — 原地读取并过滤，**不搬动、不拷贝**。原语（backup / restore / apply）不感知：

| 阶段 | 操作 | 归属 |
|------|------|:---:|
| 过滤 | 解析 `.kmmignore`（gitignore 语法），在 `plan_fileops()` 中现场读取并过滤被忽略的文件 | Planner |
| 不备份 | `.kmmignore` 不进入备份流程 | — |
| 不恢复 | 恢复操作不触碰 `.kmmignore` | — |

理由（2026-06-03）：modmgr 只有两个状态（原始态 / 被替换态），不存在多版本历史需追踪 `.kmmignore`。改写后下次 Planner 执行时当场生效。

---

## 二、黑箱测试断言

### 2.1 拷贝函数不存在

| # | 断言 | 级别 |
|---|------|:---:|
| T-KI-01 | 代码库中**任何模块**不含 `_copy_kmmignore_to_backup` 函数定义 | MUST |
| T-KI-02 | 代码库中**任何模块**不含 `_copy_kmmignore_from_backup` 函数定义 | MUST |
| T-KI-03 | `orchestrator/__init__.py` 不调用任何 `.kmmignore` 拷贝函数 | MUST |
| T-KI-04 | `orchestrator/fileops/planner/planner.py` 不执行任何 `.kmmignore` 文件写入（`shutil.copy` / `shutil.copy2` 等） | MUST |
| T-KI-05 | `backup_ops.py` 不 import 任何 `.kmmignore` 相关模块或函数 | MUST |
| T-KI-06 | `restore_ops.py` 不 import 任何 `.kmmignore` 相关模块或函数 | MUST |

### 2.2 原地过滤行为

| # | 断言 | 级别 |
|---|------|:---:|
| T-KI-07 | `plan_fileops()` 读取源目录中存在的 `.kmmignore` 文件（而非从 backup_dir 读取） | MUST |
| T-KI-08 | `plan_fileops()` 返回的 `FileOpsPlan.entries_by_backup_dir` 不含被 `.kmmignore` 忽略的文件 | MUST |
| T-KI-09 | `plan_fileops()` 输出中的 `ignore_rule_set` 缓存可供原语直接消费 | MUST |
| T-KI-10 | 源目录无 `.kmmignore` → 过滤结果为空 ignore 集，不报错 | MUST |

### 2.3 .kmmignore 不搬动

| # | 断言 | 级别 |
|---|------|:---:|
| T-KI-11 | backup 操作后 `backup_dir` 中不含 `.kmmignore` 文件（不被拷贝） | MUST |
| T-KI-12 | restore 操作后源目录 `.kmmignore` 内容不变（不被覆盖/还原） | MUST |
| T-KI-13 | `.kmmignore` 拷贝失败的错误码和 warning 不再存在 | SHOULD |

### 2.4 文档一致性

| # | 断言 | 级别 |
|---|------|:---:|
| T-KI-14 | `DESIGN_BACKUP_OPS.md §十三` 描述 `.kmmignore` 原地生效，不搬动 | MUST |
| T-KI-15 | `DESIGN_RESTORE_OPS.md §八` 不描述 restore 原语操作 `.kmmignore` | MUST |
| T-KI-16 | `DESIGN_PLANNER.md` 描述 `.kmmignore` 原地过滤职责 | MUST |

---

## 三、验收标准

- [ ] 全部 T-KI-01 ~ T-KI-16 通过
- [ ] `fileops/__init__.py:execute()` 不操作 `.kmmignore` 文件
- [ ] 现有备份/还原测试不受影响

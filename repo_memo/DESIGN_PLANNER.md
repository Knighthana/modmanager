# DESIGN_PLANNER — fileops 总调度器设计

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 Planner（`planner_fileops.py`）作为 fileops 总调度器的职责边界、输入输出契约、与原语的关系
> 创建: 2026-06-02
> 关联: 裁定 1/13/14

---

## 一、定位

Planner 是 `fileops` 的总调度器，位于 orchestrator 与原语之间：

```
orchestrator dispatch()
    │
    ├─ resolve (bootstrap) → CleanContext
    ├─ planner → FileOpsPlan        ← 本模块
    │     ├─ .kmmignore 过滤 + 物理拷贝
    │     ├─ gate / preflight 决策
    │     └─ 下发任务清单
    └─ primitives (backup / apply / restore)
          └─ 只执行最简单操作，不感知 ignore / gate
```

Planner 是 orchestrator 的下属成员，位于 `src/modmgr/orchestrator/planner_fileops.py`。

---

## 二、职责

### 2.1 核心产出：`FileOpsPlan`

`plan_fileops(clean_context, intent, flags)` 返回一个 `FileOpsPlan`，包含：

- `backup_dirs`：本次操作涉及的 backup 目录列表
- `entries_by_backup_dir`：按 backup_dir 分组的操作条目
- `preflight_manifest`：前置门禁检查结果
- `ignore_rule_set`：缓存的 ignore 规则集（供原语直接消费）
- `dry_run`：透传标志

### 2.2 `.kmmignore` 文件完整生命周期

Planner **全权管理** `.kmmignore` 文件：

| 阶段 | 操作 | 说明 |
|------|------|------|
| **过滤** | `ignore_rules.py` 解析 `.kmmignore`，在 `plan_fileops()` 中过滤被忽略的文件 | 已实现 |
| **备份时拷贝** | `_copy_kmmignore_to_backup()`：从源目录各级祖先收集 `.kmmignore`，拷贝到 `backup_dir` 对应位置 | 从 orchestrator 迁入 |
| **还原时拷贝** | `_copy_kmmignore_from_backup()`：从 `backup_dir` 各级目录收集 `.kmmignore`，拷贝回源目录对应位置 | 从 orchestrator 迁入 |

原语（backup / restore / apply）**不感知** `.kmmignore` 文件的存在。ignore 规则集通过 `FileOpsPlan.ignore_rule_set` 缓存在 plan 中，原语直接消费，不重新计算。

### 2.3 Gate / Preflight 逻辑

Planner 及附属部件（`preflight.py`）**独占**所有 gate 决策逻辑：

| 函数 | 原位置 | 新位置 | 说明 |
|------|--------|--------|------|
| `check_backup_gate()` | `backup_ops.py` | `planner_fileops.py` 或 `preflight.py` | 备份门禁：检查 backup_dir 可恢复性 |
| `run_apply_preflight()` | `preflight.py`（已有） | `preflight.py`（不变） | apply 前置门禁 |
| `run_restore_preflight()` | `preflight.py`（已有） | `preflight.py`（不变） | restore 前置门禁 |

原语**不持有**任何 gate / preflight 逻辑。原语只接收 Planner 已过滤的任务清单并执行。

### 2.4 任务清单下发

Planner 在屏蔽所有无关信息后，将操作任务清单下发给原语：

- **给 backup 原语**：scope（哪些文件需要备份）+ ignore 缓存 + backupinfo 状态
- **给 restore 原语**：scope（哪些文件需要恢复）+ ignore 缓存 + backupinfo 树
- **给 apply 原语**：scope（哪些条目需要 apply）+ 源/目标路径映射

原语只做最简单的事——按任务清单执行文件操作，不感知 ignore、gate、kmmignore 文件。

---

## 三、与原语的关系

Planner 是原语的**信息屏蔽层**：

```
Planner                    → 原语
  ┌──────────────────┐        ┌──────────────────┐
  │ kmmignore 过滤   │  ╳     │ 原语不感知       │
  │ kmmignore 拷贝   │  ╳     │ 原语不感知       │
  │ gate 门禁        │  ╳     │ 原语不感知       │
  │ scope 决策       │  ✓     │ 消费任务清单     │
  │ ignore 规则集    │  ✓     │ 缓存到 plan 中消费│
  │ 任务清单         │  ✓     │ 按清单执行       │
  └──────────────────┘        └──────────────────┘
```

原语之间**互不知晓**（L1 硬约束），Planner 是各原语的唯一信息源。

---

## 四、与 orchestrator 的关系

`dispatch()` 在 resolve 之后调用 Planner：

```python
def dispatch(request, *, on_progress=None):
    # 1. Resolve → CleanContext
    ctx = resolve(request)
    # 2. Planner → FileOpsPlan
    plan = plan_fileops(ctx, request.intent, request.flags)
    # 3. Gate check (apply / restore)
    if not plan.preflight_manifest.ok:
        return build_preflight_result(plan)
    # 4. Execute primitive
    return execute_plan(plan, on_progress)
```

Planner 不负责：
- 资源解析（resolver 的职责）
- 实际文件操作（原语的职责）
- 进度回调协议（`ProgressCallback`，但透传 `on_progress`）
- orchestrator 的入口路由决策

---

## 五、附属部件

| 部件 | 文件 | 职责 |
|------|------|------|
| Planner 核心 | `orchestrator/planner_fileops.py` | `plan_fileops()` + `.kmmignore` 物理拷贝 |
| Ignore 规则引擎 | `orchestrator/ignore_rules.py` | `.kmmignore` 解析（gitignore 语法） |
| Preflight | `orchestrator/preflight.py` | 门禁检查（apply / restore），不含 gate 决策 |
| Gate 逻辑 | `planner_fileops.py` 或 `preflight.py` | `check_backup_gate()` 及其他 gate 函数 |

---

## 六、测试断言

- `.kmmignore` 过滤：被 ignore 的文件不出现在 `FileOpsPlan.entries_by_backup_dir` 中
- `.kmmignore` 物理拷贝：backup 后 `backup_dir` 对应位置存在 `.kmmignore` 文件；restore 后源目录对应位置恢复 `.kmmignore`
- gate check：`backup_dir` 不可恢复时 `preflight_manifest.ok == false`
- 任务清单：原语收到的 `entries_by_backup_dir` 中无不相关文件
- 原语不 import `planner_fileops`、`preflight`、`ignore_rules`（解耦验证）
- `check_backup_gate` 不在 `backup_ops.__all__` 中

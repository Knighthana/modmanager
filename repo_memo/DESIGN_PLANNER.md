# DESIGN_PLANNER — fileops 总调度器设计

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 Planner（`fileops/__init__.py:execute()`）作为 fileops 总调度器的职责边界、输入输出契约、与原语的关系
> 创建: 2026-06-02
> 更新: 2026-06-03（DataPort 引入 + kmmignore 原地规则）
> 关联: 裁定 1/13/14, PLAN_DATAPORT

---

## 一、定位

Planner 是 `fileops` 的总调度器，位于 DataPort 与原语之间：

```
orchestrator dispatch()
    │
    ├─ Resolver.resolve() → SourceDescriptor       （纯解析，无 I/O）
    ├─ DataPort.fetch()   → clean dicts            （唯一 I/O 通道）
    ├─ fileops.execute()  → PipelineResult         ← 本模块
    │     ├─ plan_fileops()：过滤 + gate + 计划
    │     │     ├─ .kmmignore 原地读取并过滤
    │     │     └─ gate / preflight 决策
    │     └─ 下发任务清单 + 执行原语
    └─ DataPort.push()    （若需要持久化）
```

Planner 的入口 `execute()` 位于 `src/modmgr/orchestrator/fileops/__init__.py`。核心规划逻辑位于 `fileops/planner/planner.py`。

---

## 二、职责

### 2.1 入口：`fileops.execute()`

```python
def execute(data: dict, intent: Intent, flags: dict, on_progress=None) -> PipelineResult:
    """Planner 统一入口。接收 DataPort 产出的 clean dict，完成 plan → gate → execute 全链。"""
    plan = plan_fileops(data, intent, flags, on_progress=on_progress)
    if not plan.preflight_manifest.ok:
        return build_preflight_result(plan)
    return _execute_plan(plan, on_progress)
```

### 2.2 核心产出：`FileOpsPlan`

`plan_fileops(data, intent, flags)` 返回一个 `FileOpsPlan`，包含：

- `backup_dirs`：本次操作涉及的 backup 目录列表
- `entries_by_backup_dir`：按 backup_dir 分组的操作条目
- `preflight_manifest`：前置门禁检查结果
- `ignore_rule_set`：原地读取 `.kmmignore` 后缓存的结果（供原语直接消费）
- `dry_run` / `force` / `warnings`：透传标志

### 2.3 `.kmmignore`：原地规则（In-place）

Decision 2026-06-03: `.kmmignore` 始终原地生效，**不搬动、不拷贝**。

- **过滤**：`plan_fileops()` 中通过 `ignore_rules.py` 解析各级 `.kmmignore` 文件，就地读取后过滤被忽略的文件。结果写入 `FileOpsPlan.ignore_rule_set`
- **不备份**：`.kmmignore` 文件不进入备份流程
- **不恢复**：恢复操作不触碰 `.kmmignore` 文件

理由：modmgr 只有两个状态（原始态 / 被替换态），不存在多版本历史需要追踪 `.kmmignore`。改写 `.kmmignore` 后下次 Planner 执行时当场生效。

原语对 `.kmmignore` **无感知**——不 import、不操作、不决策。

### 2.4 Gate / Preflight 逻辑

Planner 及附属部件（`fileops/planner/preflight.py`）**独占**所有 gate 决策逻辑：

| 函数 | 原位置 | 新位置 | 说明 |
|------|--------|--------|------|
| `check_backup_gate()` | `backup_ops.py` | `fileops/planner/planner.py` 或 `fileops/planner/preflight.py` | 备份门禁：检查 backup_dir 可恢复性 |
| `run_apply_preflight()` | `preflight.py` | `fileops/planner/preflight.py` | apply 前置门禁 |
| `run_restore_preflight()` | `preflight.py` | `fileops/planner/preflight.py` | restore 前置门禁 |

原语**不持有**任何 gate / preflight 逻辑。

### 2.5 任务清单下发

Planner 屏蔽所有无关信息后下发任务清单：

- **给 backup 原语**：scope（哪些文件需要备份）+ ignore 缓存 + backupinfo 状态
- **给 restore 原语**：scope（哪些文件需要恢复）+ ignore 缓存 + backupinfo 树
- **给 apply 原语**：scope（哪些条目需要 apply）+ 源/目标路径映射

原语只按清单执行文件操作，不感知 ignore、gate、kmmignore。

---

## 三、与原语的关系

Planner 是原语的**信息屏蔽层**：

```
Planner                    → 原语
  ┌──────────────────┐        ┌──────────────────┐
  │ kmmignore 过滤   │  ╳     │ 原语不感知       │
  │ gate 门禁        │  ╳     │ 原语不感知       │
  │ scope 决策       │  ✓     │ 消费任务清单     │
  │ ignore 规则集    │  ✓     │ 缓存到 plan 中消费│
  │ 任务清单         │  ✓     │ 按清单执行       │
  └──────────────────┘        └──────────────────┘
```

原语之间**互不知晓**（L1 硬约束），Planner 是各原语的唯一信息源。

---

## 四、与 orchestrator 的关系

`dispatch()` 经 DataPort 后调用 Planner：

```python
def dispatch(request, *, on_progress=None):
    # 1. Resolve → SourceDescriptor（纯解析，无 I/O）
    desc = resolver.resolve(request)
    # 2. DataPort.fetch → clean dicts（唯一 I/O）
    data = data_port.fetch(desc, request.intent)
    # 3. Planner → PipelineResult（plan → gate → execute）
    result = fileops.execute(data, request.intent, request.flags, on_progress)
    # 4. DataPort.push（若需要持久化，如 workspace compute）
    if needs_push:
        data_port.push(desc, request.intent, result)
    return result
```

Planner 不负责：
- 资源解析（resolver 的职责）
- 数据 I/O（DataPort 的职责）
- orchestrator 的入口路由决策

---

## 五、附属部件

| 部件 | 文件 | 职责 |
|------|------|------|
| Planner 入口 | `orchestrator/fileops/__init__.py` | `execute()`：plan → gate → execute 全链 |
| Planner 核心 | `orchestrator/fileops/planner/planner.py` | `plan_fileops()` + `.kmmignore` 原地过滤 |
| Ignore 规则引擎 | `orchestrator/fileops/planner/ignore_rules.py` | `.kmmignore` 解析（gitignore 语法） |
| Preflight | `orchestrator/fileops/planner/preflight.py` | 门禁检查（apply / restore） |
| Gate 逻辑 | `fileops/planner/planner.py` | `check_backup_gate()` |

---

## 六、测试断言

- `.kmmignore` 过滤：被 ignore 的文件不出现在 `FileOpsPlan.entries_by_backup_dir` 中
- `.kmmignore` 原地：`.kmmignore` 物理拷贝代码不存在于任何模块中；Planner 中只读取不写入 `.kmmignore`
- gate check：`backup_dir` 不可恢复时 `preflight_manifest.ok == false`
- 任务清单：原语收到的 `entries_by_backup_dir` 中无不相关文件
- 原语不 import `planner_fileops`、`preflight`、`ignore_rules`（解耦验证）
- `check_backup_gate` 不在 `backup_ops.__all__` 中

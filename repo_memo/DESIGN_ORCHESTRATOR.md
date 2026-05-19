# DESIGN_ORCHESTRATOR — Orchestrator 流水线调度

> Status: stable
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 orchestrator 的调度职责、阶段串联方式与 CLI/GUI 共享入口边界

> 来源：DESIGN_BOOTSTRAP_ORCHESTRATOR.md（orchestrator 部分）
> 更新：2026-05-16 — 新增 workspacemanager 下属；compute/run 接收 workspace_id 参数，从工作区读取规则与决策
> 更新：2026-05-18 — engine/_ws 职责分离：引擎函数接收消费品 (final_mapping, database, user_config, flags)，内部调 build_backup_dirs；_ws 函数翻译工作区语境 → 委托引擎；新增 restore() / restore_ws()
> 实现状态：已落地并持续生效

---

## 一、定位

Orchestrator 负责流水线调度、进度回调、多阶段串联。它是唯一的调度入口，CLI 和 GUI 都通过它驱动流程，确保行为一致。

```
                     ┌─────────────────────┐
        CLI / GUI →  │    orchestrator      │  统一调度入口
                     │  (run / compute /    │
                     │   backup / apply)    │
                     └──────────┬──────────┘
                                │
           ┌────────────────────┼────────────────────┐
           ▼                    ▼                    ▼
     bootstrap           workspacemanager        backup_ops
  (环境初始化：          (工作区 CRUD：         (备份/替换/恢复)
   user_config /         规则/决策/结果/
   database)             SVG 读写)
           │                    │
           └────────┬───────────┘
                    │
          ┌─────────┼─────────┐
          ▼                   ▼
     aggregator            engine
    (规则聚合)           (映射计算)
```

**文件**：`src/modmanager/orchestrator.py`

---

## 二、进度回调协议

```python
from typing import Protocol

class ProgressCallback(Protocol):
    def __call__(self, step: str, finished: int, total: int, message: str = "") -> None:
        """进度通知。

        Args:
            step: 阶段标识 ("scan" | "aggregate" | "compute" | "backup" | "apply" | "restore")
            finished: 已完成数量
            total: 总量（-1 表示未知）
            message: 可选的描述文本
        """
        ...
```

---

## 三、公共接口

### PipelineResult

```python
@dataclass
class PipelineResult:
    """流水线执行结果"""
    ok: bool
    errors: list[str]
    warnings: list[str]
    trees: list[dict[str, Any]]           # 映射树数组
    final_mapping: list[dict[str, Any]]    # 最终映射
    mapping_result: dict[str, Any]          # compute_mapping 原始输出
    backup_result: dict[str, Any] | None    # 来自 run_differential_backup
    apply_result: dict[str, Any] | None     # 来自 apply_final_mapping
    restore_result: dict[str, Any] | None   # 来自 restore_from_backup
    backup_dir: str | None = None
```

### 引擎函数（纯逻辑，不感知工作区）

引擎函数接收消费品 `(final_mapping, database, user_config, flags)`。需要 backup_dir 时内部调 `build_backup_dirs`，不依赖外部传入。

#### compute()

```python
def compute(
    database: dict,
    *,
    aggregated_rule_set: dict | None = None,
    action_orders: dict[str, int] | None = None,
    branch_decisions: dict[str, str] | None = None,
    managed_entries: dict | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """计算文件映射。"""
```

#### backup()

```python
def backup(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """差异备份。内部调 build_backup_dirs 推导目录，逐目录过滤 bakignore 后执行。"""
```

#### apply()

```python
def apply(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """应用映射。内部调 build_backup_dirs 推导目录，逐目录 gate check 后执行。"""
```

#### restore()

```python
def restore(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
    *,
    force: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """恢复文件。独立原语，与 backup 解耦。内部调 build_backup_dirs 推导目录，
    读 backupinfo.json 比对 HASH（force=True 时跳过比对）。"""
```

#### run()

```python
def run(
    database: dict,
    aggregated_rule_set: dict,
    managed_entries: dict | None,
    branch_decisions: dict[str, str] | None,
    user_config: dict[str, Any],
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """全流水线：compute → backup → apply。"""
```

### 工作区函数（翻译工作区语境 → 委托引擎）

`_ws` 函数的唯一职责：从工作区加载 mapping / database / user_config，转为消费品后委托引擎。不传 backup_dirs，不代引擎做决策。

#### compute_ws()

```python
def compute_ws(workspace_id: str, *, on_progress=None) -> PipelineResult:
    """加载聚合规则 + 决策 + database → compute() → 写 mapping/SVG 回工作区。"""
```

#### backup_ws()

```python
def backup_ws(workspace_id: str, *, dry_run=False, on_progress=None) -> PipelineResult:
    """加载 mapping + database + user_config → build_backup_dirs → backup()。"""
```

#### apply_ws()

```python
def apply_ws(workspace_id: str, *, dry_run=False, on_progress=None) -> PipelineResult:
    """加载 mapping + database + user_config → apply()。"""
```

#### restore_ws()

```python
def restore_ws(workspace_id: str, *, force=False, on_progress=None) -> PipelineResult:
    """加载 mapping + database + user_config → restore()。"""
```

#### run_ws()

```python
def run_ws(workspace_id: str, *, dry_run=False, on_progress=None) -> PipelineResult:
    """加载工作区全部上下文 → run()。"""
```

---

## 四、内部流程

### run() 引擎函数

```
run(database, aggregated_rule_set, managed_entries, branch_decisions, user_config, dry_run, on_progress)
  │
  ├─ compute(database, aggregated_rule_set, managed_entries, branch_decisions, on_progress)
  │
  ├─ [dry_run?] → 返回 compute 结果（跳过备份和应用）
  │
  ├─ backup(final_mapping, database, user_config, dry_run, on_progress)
  │     ├─ build_backup_dirs(final_mapping, database, user_config)
  │     ├─ 逐目录：bakignore 过滤 → run_differential_backup
  │     └─ 拷贝 .kmmbakignore 进 backup_dir
  │
  └─ apply(final_mapping, database, user_config, dry_run, on_progress)
        ├─ build_backup_dirs(final_mapping, database, user_config)
        ├─ 逐目录：gate check → apply_final_mapping
        └─ 拷贝 .kmmbakignore 回源目录
```

### _ws 函数流程

```
run_ws(workspace_id, dry_run, on_progress)
  │
  ├─ compute_ws(workspace_id, on_progress)
  │     └─ ws.read_aggregated_rule / ws.read_decisions
  │        → compute(database, ...) → ws.write_mapping / ws.write_svg
  │
  ├─ backup_ws(workspace_id, dry_run, on_progress)
  │     └─ ws.read_mapping / _resolve_database
  │        → build_backup_dirs → backup(...)
  │
  └─ apply_ws(workspace_id, dry_run, on_progress)
        └─ ws.read_mapping / _resolve_database
           → apply(...)
```

---

## 五、错误处理

- 任一步骤失败（errors 非空）→ 停止后续步骤，返回当前状态
- engine 函数不负责生成 `backup_dir` 命名——内部调 `backup_dir_builder.build_backup_dirs`
- `_ws` 函数不传 backup_dirs——引擎自己算
- gate check 失败不阻塞其他 backup_dir 的处理

---

## 六、CLI 改动

现有 `cli.py` 的编排逻辑迁移到 orchestrator：

| 旧代码 | 新代码 |
|--------|--------|
| `_handle_backup()`: → compute_mapping → run_differential_backup | 调用 `orchestrator.backup()` |
| `_handle_apply()`: → compute_mapping → apply_final_mapping | 调用 `orchestrator.apply()` |
| 主 compute 模式（无子命令时） | 调用 `orchestrator.compute()` |

CLI 变为薄壳：解析参数 → 调用 orchestrator → 格式化输出。

---

## 七、与现有代码的关系

| 模块 | 改动 |
|------|------|
| `engine.py` | 无改动 |
| `aggregator.py` | 无改动 |
| `backup_ops.py` | 无改动 |
| `cli.py` | 编排逻辑迁移到调用 orchestrator |
| `cli-hmi/run.py` | 可替换为调用 orchestrator（非必须） |

---

## 八、实现顺序

```
Task 5: bootstrap.py    ← user_config 发现 + 数据库生成
Task 6: orchestrator.py ← 流水线调度
Task 7: CLI 适配        ← 改为调用 orchestrator
Task 8: 测试            ← bootstrap + orchestrator 测试
```

# DESIGN_ORCHESTRATOR — Orchestrator 流水线调度

> Status: active
> Last update: 2026-05-21 — Four-layer model (Entry → Resolver → Planner → Primitive); orchestrator/ package
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 orchestrator 的调度职责、阶段串联方式与 CLI/GUI 共享入口边界

---

## 一、定位

Orchestrator 是统一的调度入口。无论 Web API 还是 CLI，所有请求通过 `dispatch()` 进入，
由 Orchestrator 根据 `Intent` 路由到对应管线。

```
                     ┌─────────────────────────────────┐
        Web / CLI →  │         dispatch()              │  统一入口
                     │    (Intent-based routing)       │
                     └──────────────┬──────────────────┘
                                    │
              ┌─────────────────────┼──────────────────────┐
              ▼                     ▼                      ▼
      COMPUTE_MAPPING        BACKUP/APPLY/RESTORE/RUN  (未来扩展)
         │                       │
         ▼                       ▼
    Resolver.resolve()       Resolver.resolve()
    → SourceDescriptor       → SourceDescriptor
         │                       │
         ▼                       ▼
    DataPort.fetch()         DataPort.fetch()
    → clean dicts            → clean dicts
         │                       │
         ▼                       ▼
    Engine.compute()         fileops.execute()
    → PipelineResult         → plan → gate → execute
         │                       │
         ▼                       ▼
    DataPort.push()          PipelineResult
    (workspace only)
```

Orchestrator 自身是星形拓扑核心，通过 `orchestrator/` 包的公开接口暴露最小表面：
`PipelineResult`、`ProgressCallback`、`dispatch`、`Intent`、`TaskRequest`。

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

**进度事件契约（SSE 隐含要求，显式写入）**：

每个执行阶段（prepare / backup / apply / restore）**必须**至少发送一次进度事件，即便该阶段无条目需处理。

- 阶段开始时：发送 `finished=0, total=N`（N 为条目数，无条目时 `total=1`）
- 阶段结束时：发送 `finished=N, total=N`（最终进度）
- 禁止出现「零进度事件直接返回 result」的情况——前端依赖首个 `progress` 确认工作已启动，若永远等不到则 UI 卡在「准备中...」

各阶段推荐的 step 标识：

| 阶段 | step 值 | 说明 |
|------|---------|------|
| 准备 | `"prepare"` | Resolve → Plan（4 子步）→ Preflight → Ready，共 6 个子阶段 |
| 备份 | `"backup"` | fileops 执行备份阶段 |
| 应用 | `"apply"` | fileops 执行应用阶段 |
| 恢复 | `"restore"` | fileops 执行恢复阶段 |
| 全流水线 | `"run"` | 组合备份+应用，逐阶段发送 |

---

## 三、公开接口

### dispatch()

```python
def dispatch(request: TaskRequest, *, on_progress=None) -> PipelineResult:
    """统一入口。根据 request.intent 路由到对应管线。"""
```

### TaskRequest

```python
@dataclass
class TaskRequest:
    identity: Literal["web", "cli"]
    intent: Intent            # COMPUTE_MAPPING | BACKUP | APPLY | RESTORE | RUN
    resolver_type: Literal["workspace", "file_paths", "raw_dict"]
    resolver_args: dict       # fetch 来源参数
    output_type: Literal["workspace", "none"] = "none"    # push 目标类型
    output_args: dict = field(default_factory=dict)       # push 目标参数
    flags: dict               # dry_run, force, etc.
```

### PipelineResult

```python
@dataclass
class PipelineResult:
    ok: bool
    errors: list[str]
    warnings: list[str]
    trees: list[dict]
    final_mapping: list[dict]
    mapping_result: dict
    backup_result: dict | None
    apply_result: dict | None
    restore_result: dict | None
    workspace_id: str | None    # [planned] 替代 backup_dir——返回 workspace 标识符而非文件路径
```

内部契约（`dry_run` 穿透、适配器同步、`__post_init__` 校验）见 `DESIGN_ORCHESTRATOR_CONTRACT.md`。

---

## 四、内部流程

### dispatch() 路由

```
dispatch(request)
  │
  ├─ intent=COMPUTE_MAPPING
  │     ├─ 1. Resolver.resolve() → SourceDescriptor
  │     ├─ 2. DataPort.fetch() → clean dicts
  │     ├─ 3. Engine.compute() → PipelineResult
  │     └─ 4. DataPort.push() (workspace only — write mapping/SVG/fingerprints)
  │
  └─ intent=BACKUP/APPLY/RESTORE/RUN
       │
       ├─ 1. Resolver.resolve() → SourceDescriptor
       ├─ 2. DataPort.fetch() → clean dicts
       ├─ 3. fileops.execute(data, intent, flags) → PipelineResult
       │     ├─ plan_fileops() → FileOpsPlan
       │     ├─ preflight gate check
       │     └─ execute primitive (backup / apply / restore / run)
       └─ 4. PipelineResult → 返回调用方
```

---

## 五、错误处理

- 任一步骤失败（errors 非空）→ 停止后续步骤，返回当前状态
- Resolver / Planner / Preflight / Primitive 各层独立汇报错误，不跨层吞没
- `dispatch()` 负责组装各层结果到 `PipelineResult`；非 `COMPUTE_MAPPING` 管线若 preflight 失败
  则返回 preflight 结果，不执行原语

---

## 八、模块映射

**文件操作层（fileops）**：
- Planner 入口（`orchestrator/fileops/__init__.py`）：`execute()` 统一入口，负责 plan → gate → execute 全链
- Planner 核心（`orchestrator/fileops/planner/planner.py`）：`plan_fileops()` + `.kmmignore` 原地过滤：`plan_fileops()`、`.kmmignore` 原地过滤、gate/preflight 调度
- preflight（`orchestrator/fileops/planner/preflight.py`）：门禁检查

| 模块 | 文件 | 职责 |
|------|------|------|
| Orchestrator 核心 | `orchestrator/__init__.py` | `dispatch()` 入口 + `PipelineResult` |
| Entry | `orchestrator/entry.py` | `TaskRequest` + `Intent` enum |
| Resolver | `orchestrator/resolver.py` | `SourceDescriptor` + `WorkspaceResolver` / `FilePathResolver` / `RawDictResolver`（纯解析，无 I/O） |
| **DataPort** | `orchestrator/data_port.py` | `fetch()` + `push()` — 唯一 I/O 通道 |
| Planner 入口 | `orchestrator/fileops/__init__.py` | `execute()`：plan → gate → execute |
| Planner 核心 | `orchestrator/fileops/planner/planner.py` | `plan_fileops()` + `.kmmignore` 原地过滤 |
| Ignore 规则 | `orchestrator/fileops/planner/ignore_rules.py` | `collect_rules()`, `should_ignore()` |
| Preflight | `orchestrator/fileops/planner/preflight.py` | 门禁检查 |
| Compute 引擎 | `orchestrator/compute_pipeline.py` | `compute()` — 映射生产 |
| Database 管理 | `database_ops.py` | orchestrator 一等成员：database 发现、生成、校验、CRUD |
| 共享设施 | `orchestrator/_common.py` | 共享 helper |
| Backup 原语 | `backup_ops.py` | `run_differential_backup()` |
| Restore 原语 | `restore_ops.py` | `restore_entries()` |
| Apply 原语 | `apply_ops.py` | `apply_entries()` |
```

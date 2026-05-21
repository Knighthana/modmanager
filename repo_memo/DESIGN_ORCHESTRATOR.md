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
     compute_pipeline         Entry → Resolver        (未来扩展)
     (映射生产)               → Planner → Primitive
                              (文件操作四层)
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
| 备份 | `"backup"` | `_execute_backup_plan` |
| 应用 | `"apply"` | `_execute_apply_plan` |
| 恢复 | `"restore"` | `_execute_restore_plan` |
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
    resolver_args: dict       # opaque — Resolver 自决语义
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
    backup_dir: str | None
```

---

## 四、内部流程

### dispatch() 路由

```
dispatch(request)
  │
  ├─ intent=COMPUTE_MAPPING → compute_pipeline.compute()
  │
  └─ intent=BACKUP/APPLY/RESTORE/RUN
       │
       ├─ 1. Select Resolver (WorkspaceResolver / FilePathResolver / RawDictResolver)
       ├─ 2. Resolve → CleanContext {final_mapping, database, user_config}
       ├─ 3. Planner → FileOpsPlan {backup_dirs, entries_by_backup_dir, preflight, ...}
       ├─ 4. Preflight gate check (apply / restore only)
       └─ 5. Execute primitive
            ├─ apply_ops.apply_entries()
            ├─ restore_ops.restore_entries()
            ├─ backup_ops.run_differential_backup()
            └─ run = backup + apply (no preflight)
```

---

## 五、错误处理

- 任一步骤失败（errors 非空）→ 停止后续步骤，返回当前状态
- Resolver / Planner / Preflight / Primitive 各层独立汇报错误，不跨层吞没
- `dispatch()` 负责组装各层结果到 `PipelineResult`；非 `COMPUTE_MAPPING` 管线若 preflight 失败
  则返回 preflight 结果，不执行原语

---

## 八、模块映射

| 模块 | 文件 | 职责 |
|------|------|------|
| Orchestrator 核心 | `orchestrator/__init__.py` | `dispatch()` 入口 + `PipelineResult` + 执行辅助函数 |
| Entry | `orchestrator/entry.py` | `TaskRequest` + `Intent` enum |
| Resolver | `orchestrator/resolver.py` | `CleanContext` + `WorkspaceResolver` / `FilePathResolver` / `RawDictResolver` |
| Planner (文件操作) | `orchestrator/planner_fileops.py` | `FileOpsPlan` + `plan_fileops()` |
| Preflight | `orchestrator/preflight.py` | `run_apply_preflight()` / `run_restore_preflight()` |
| Compute 管线 | `orchestrator/compute_pipeline.py` | `compute()` / `compute_ws()` (映射生产) |
| 共享设施 | `orchestrator/_common.py` | `PipelineResult` dataclass, 共享 helper |
| Apply 原语 | `apply_ops.py` | `apply_entries()` — file-to-file apply |
| Restore 原语 | `restore_ops.py` | `restore_entries()` — file-to-file restore |
| Backup 原语 | `backup_ops.py` | `run_differential_backup()` — differential backup |
```

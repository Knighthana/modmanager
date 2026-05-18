# DESIGN_ORCHESTRATOR — Orchestrator 流水线调度

> Status: stable
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 orchestrator 的调度职责、阶段串联方式与 CLI/GUI 共享入口边界

> 来源：DESIGN_BOOTSTRAP_ORCHESTRATOR.md（orchestrator 部分）
> 更新：2026-05-16 — 新增 workspacemanager 下属；compute/run 接收 workspace_id 参数，从工作区读取规则与决策
> 更新：2026-05-18 — backup() 函数签名新增 dry_run 参数；新增 backup_ws / apply_ws 工作区感知函数；on_progress 支持逐文件进度回调
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
```

### compute()

```python
def compute(
    workspace_id: str,
    *,
    action_orders: dict[str, int] | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """在工作区上下文中执行计算映射。
    聚合规则集和用户决策从 workspacemanager 的工作区目录读取。
    database 路径从工作区 meta.json 的 database_name 查 user_config 获取。
    计算结果（mapping + SVG + 指纹）由 workspacemanager 写入工作区目录。
    返回 PipelineResult（backup_result 和 apply_result 为 None）。
    """
```

### backup()

```python
def backup(
    mapping_result: dict[str, Any],
    backup_dir: str,
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """对 final_mapping 中的文件执行差异备份。
    dry_run=True 时不执行文件 I/O，仅返回预期操作列表。"""
```

### apply()

```python
def apply(
    final_mapping: list[dict[str, Any]],
    backup_dir: str,
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """执行 final_mapping 的磁盘替换。"""
```

### run() — 全流水线

```python
def run(
    workspace_id: str,
    backup_dir: str,
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """全流水线：计算 → 备份 → 应用。
    聚合规则集和用户决策从 workspacemanager 的工作区目录读取。
    database 路径从工作区 meta.json 的 database_name 查 user_config 获取。
    等价于依次调用 compute() + backup() + apply()。
    """
```

---

## 四、内部流程

```
run(workspace_id, backup_dir, *, dry_run=False, ...)
  │
  ├─ 0. 环境初始化
  │     ws = workspacemanager
  │     meta = ws.read_meta(workspace_id)
  │     bootstrap 获取 user_config + database（通过 meta.database_name）
  │     on_progress("bootstrap", 1, 1)
  │
  ├─ 1. 读取工作区数据
  │     aggregated_rule_set = ws.read_aggregated_rule(workspace_id)
  │     decisions = ws.read_decisions(workspace_id)
  │     on_progress("load", 1, 1)
  │
  ├─ 2. 计算映射
  │     database = _apply_managed_filter(database, decisions.managed_entries)
  │     mapping_result = compute_mapping(aggregated_rule_set, database, decisions.branch_decisions)
  │     on_progress("compute", 1, 1)
  │
  ├─ [dry_run?] ─────────────────────────────────────────────────────────────
  │     是 → ws.write_mapping(workspace_id, mapping_result)
  │           ws.write_fingerprints(workspace_id, {...})
  │           直接返回 compute 结果（跳过备份和应用）
  │     否 → 继续
  │
  ├─ 3. 写入结果
  │     ws.write_mapping(workspace_id, mapping_result)
  │     ws.write_svg(workspace_id, svg)
  │     ws.write_fingerprints(workspace_id, {...})
  │
  ├─ 4. 差异备份
  │     backup_result = run_differential_backup(backup_dir, files)
  │     on_progress("backup", i, total)
  │
  └─ 5. 应用替换
        apply_result = apply_final_mapping(final_mapping, backup_dir, dry_run)
        on_progress("apply", i, total)
```

**dry_run 语义**：当 `dry_run=True` 时，步骤 1-2 正常执行（聚合+计算），步骤 3-4 全部跳过。这意味着 dry_run 完全不触碰磁盘——不备份、不替换。

---

## 五、错误处理

- 任一步骤失败（errors 非空）→ 停止后续步骤，返回当前状态
- `backup()` 和 `apply()` 需要 `backup_dir` 参数——由调用方（CLI/GUI）决定目录路径
- orchestrator 不负责生成 `backup_dir` 命名（那是 `backup_dir_builder` 的职责）

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

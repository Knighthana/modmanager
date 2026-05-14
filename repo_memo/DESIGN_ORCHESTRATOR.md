# DESIGN_ORCHESTRATOR — Orchestrator 流水线调度

> Status: stable
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 orchestrator 的调度职责、阶段串联方式与 CLI/GUI 共享入口边界

> 来源：DESIGN_BOOTSTRAP_ORCHESTRATOR.md（orchestrator 部分）
> 更新：2026-05-14 — orchestrator 不读取 workspace；managed_entries / branch_decisions 作为可选参数接收
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
                                │ 需要环境数据时调用
                     ┌──────────▼──────────┐
                     │     bootstrap        │  环境初始化
                     │  (user_config /      │
                     │   database)          │
                     └──────────┬──────────┘
                                │
               ┌───────────────┼───────────────┐
               ▼               ▼               ▼
          aggregator        engine        backup_ops
         (规则聚合)       (映射计算)      (备份/替换/恢复)
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
    trees: list[dict[str, Any]]           # 映射森林（P0 后 forest → trees）
    final_mapping: list[dict[str, Any]]    # 最终映射
    mapping_result: dict[str, Any]          # compute_mapping 原始输出
    backup_result: dict[str, Any] | None    # 来自 run_differential_backup
    apply_result: dict[str, Any] | None     # 来自 apply_final_mapping
```

### compute()

```python
def compute(
    kmm_rule_paths: list[str] | None = None,
    *,
    aggregated_rule_path: str | None = None,  # 跳过聚合，直接加载
    database_name: str | None = None,          # 指定使用的 database，不传则用默认
    action_orders: dict[str, int] | None = None,
    branch_decisions: dict[str, str] | None = None,    # 来自前端 localStorage
    managed_entries: dict[str, dict[str, list[str]]] | None = None,  # 来自前端 localStorage
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """聚合规则 → 计算映射。database 和 user_config 由 orchestrator 内部通过 bootstrap 获取。
    不读取 workspace 文件。managed_entries 和 branch_decisions 作为可选参数直接接收。
    返回 PipelineResult（backup_result 和 apply_result 为 None）。"""
```

### backup()

```python
def backup(
    mapping_result: dict[str, Any],
    backup_dir: str,
    *,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """对 final_mapping 中的文件执行差异备份。"""
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
    kmm_rule_paths: list[str],
    backup_dir: str,
    *,
    aggregated_rule_path: str | None = None,
    database_name: str | None = None,
    action_orders: dict[str, int] | None = None,
    branch_decisions: dict[str, str] | None = None,
    managed_entries: dict[str, dict[str, list[str]]] | None = None,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """全流水线：聚合 → 计算 → 备份 → 应用。
    database 和 user_config 由 orchestrator 内部通过 bootstrap 获取。
    不读取 workspace 文件。managed_entries 和 branch_decisions 作为可选参数接收。
    等价于依次调用 compute() + backup() + apply()，
    但以 run() 作为一键入口时提供连续的进度回调。
    """
```

---

## 四、内部流程

```
run(kmm_rule_paths, backup_dir, *, dry_run=False, ...)
  │
  ├─ 0. 环境初始化
  │     bootstrap 获取 user_config + database
  │     on_progress("bootstrap", 1, 1)
  │
  ├─ 1. 聚合规则
  │     aggregated_rule_set = aggregate(kmm_rule_paths, ...)
  │     on_progress("aggregate", 1, 1)
  │
  ├─ 2. 计算映射
  │     database = _apply_managed_filter(database, managed_entries)  # managed_entries 来自参数
  │     mapping_result = compute_mapping(aggregated_rule_set, database, branch_decisions)
  │     on_progress("compute", 1, 1)
  │
  ├─ [dry_run?] ─────────────────────────────────────────────────────────────
  │     是 → 直接返回 compute 结果（跳过后续步骤，不碰磁盘）
  │     否 → 继续
  │
  ├─ 3. 差异备份
  │     backup_result = run_differential_backup(backup_dir, files)
  │     on_progress("backup", i, total)
  │
  └─ 4. 应用替换
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

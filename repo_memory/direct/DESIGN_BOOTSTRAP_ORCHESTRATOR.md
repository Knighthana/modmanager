# Bootstrap + Orchestrator 设计文档

创建：2026-04-30
状态：设计完成，待实现

---

## 1. 定位

两个新模块，填补现有底层模块（engine、aggregator、backup_ops）与上层入口（CLI、未来的 GUI）之间的编排空白。

```
                   ┌─────────────────────┐
      CLI / GUI →  │    orchestrator      │  统一调度入口
                   │  (run / compute /    │
                   │   backup / apply)    │
                   └──────────┬──────────┘
                              │ 需要初始数据时调用
                   ┌──────────▼──────────┐
                   │     bootstrap        │  环境初始化
                   │  (user_config 发现、 │
                   │   Steam DB 生成)      │
                   └──────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         aggregator        engine        backup_ops
        (规则聚合)       (映射计算)      (备份/替换/恢复)
```

- **orchestrator**：唯一的调度入口。CLI 和 GUI 都通过它驱动流程，确保行为一致。
- **bootstrap**：纯粹的环境初始化。可被 orchestrator 调用，也可被测试/外部独立调用。
- 现有底层模块不感知 orchestrator 和 bootstrap 的存在，保持独立可测试。

---

## 2. Bootstrap 模块

**文件**：`src/modmanager_cli/bootstrap.py`

### 2.1 `discover_user_config()`

```
三级搜索链（后者覆盖前者）：
  1. ~/.config/kmm/user_config.json      （最低优先级）
  2. <软件本体目录>/user_config.json       （中优先级）
  3. $PWD/user_config.json                （最高优先级）

软件本体目录 = 包含 pyproject.toml 的最近父目录（开发模式）
             或 site-packages/modmanager_cli/（pip 安装后）
             自动检测：从 __file__ 向上查找 pyproject.toml，未找到则 fallback 到 site-packages 路径
```

```python
def discover_user_config(home_dir: str | None = None) -> dict:
    """搜索三级 user_config.json 并按层级合并。

    合并规则：后者覆盖前者（dict 级别 shallow merge）。

    Returns:
        合并后的 user_config 字典
    Raises:
        FileNotFoundError: 若三级搜索均未找到任何 user_config.json
    """
```

### 2.2 `generate_database()`

```python
def generate_database(
    mode: str,
    *,
    paths: list[str] | None = None,
    working_pathstyle: str = "linux",
    greedy_parsing: bool = False,
    on_progress: ProgressCallback | None = None,
    cache_path: str | None = None,
) -> dict:
    """生成或加载 Steam 数据库。

    Args:
        mode:
            "auto"  — 自动发现 Steam 库路径，调用 steam_scanner
            "manual" — 手动模式，paths 必须传入（vdf 文件路径 或 steamapps 目录路径）
        paths: manual 模式下的路径列表
        working_pathstyle: "linux" | "windows"
        greedy_parsing: 是否放宽 mod 解析范围
        on_progress: 进度回调
        cache_path: 若提供，优先从此路径加载缓存；生成后写入此路径

    Returns:
        database 字典，格式兼容 engine.compute_mapping 的 database 输入
    """
```

**缓存策略**：只缓存生成成功的数据库（`mode="auto"` 扫描成功后写入 `cache_path`；下次调用时若 `cache_path` 存在且有效则直接加载）。

**软件本体目录的确定**（供 user_config 搜索、log 目录定位用）：
```python
def _detect_software_dir() -> str:
    """从 __file__ 向上查找 pyproject.toml。
    找到则返回该目录（开发模式），否则返回 site-packages/modmanager_cli/。
    """
```

---

## 3. Orchestrator 模块

**文件**：`src/modmanager_cli/orchestrator.py`

### 3.1 进度回调协议

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

### 3.2 公共接口

```python
@dataclass
class PipelineResult:
    """流水线执行结果"""
    ok: bool
    errors: list[str]
    warnings: list[str]
    forest: list[dict[str, Any]]           # 映射森林
    final_mapping: list[dict[str, Any]]    # 最终映射
    mapping_result: dict[str, Any]          # compute_mapping 原始输出
    backup_result: dict[str, Any] | None    # 来自 run_differential_backup
    apply_result: dict[str, Any] | None     # 来自 apply_final_mapping


def compute(
    database: dict,
    kmm_rule_paths: list[str],
    user_config_path: str,
    *,
    action_orders: dict[str, int] | None = None,
    branch_decisions: dict[str, str] | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """聚合规则 → 计算映射。返回 PipelineResult（backup_result 和 apply_result 为 None）。"""


def backup(
    mapping_result: dict[str, Any],
    backup_dir: str,
    *,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """对 final_mapping 中的文件执行差异备份。"""


def apply(
    final_mapping: list[dict[str, Any]],
    backup_dir: str,
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """执行 final_mapping 的磁盘替换。"""


def run(
    database: dict,
    kmm_rule_paths: list[str],
    user_config_path: str,
    backup_dir: str,
    *,
    action_orders: dict[str, int] | None = None,
    branch_decisions: dict[str, str] | None = None,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """全流水线：聚合 → 计算 → 备份 → 应用。

    等价于依次调用 compute() + backup() + apply()，
    但以 run() 作为一键入口时提供连续的进度回调。
    """
```

### 3.3 内部流程

```
run()
  │
  ├─ 1. 聚合规则
  │     aggregated_rule_set = aggregate(kmm_rule_paths, user_config_path, ...)
  │     on_progress("aggregate", 1, 1)
  │
  ├─ 2. 计算映射
  │     mapping_result = compute_mapping(aggregated_rule_set, database, branch_decisions)
  │     on_progress("compute", 1, 1)
  │
  ├─ 3. 差异备份
  │     backup_result = run_differential_backup(backup_dir, files)
  │     on_progress("backup", i, total)
  │
  └─ 4. 应用替换
        apply_result = apply_final_mapping(final_mapping, backup_dir, dry_run)
        on_progress("apply", i, total)
```

### 3.4 错误处理

- 任一步骤失败（errors 非空）→ 停止后续步骤，返回当前状态
- `backup()` 和 `apply()` 需要 `backup_dir` 参数——由调用方（CLI/GUI）决定目录路径
- orchestrator 不负责生成 `backup_dir` 命名（那是 `backup_dir_builder` 的职责，未来实现）

---

## 4. CLI 改动

现有 `cli.py` 的编排逻辑迁移到 orchestrator：

| 旧代码 | 新代码 |
|--------|--------|
| `_handle_backup()`: 加载文件 → compute_mapping → run_differential_backup | 调用 `orchestrator.backup()` |
| `_handle_apply()`: 加载文件 → compute_mapping → apply_final_mapping | 调用 `orchestrator.apply()` |
| 主 compute 模式（无子命令时） | 调用 `orchestrator.compute()` |

CLI 变为薄壳：解析参数 → 调用 orchestrator → 格式化输出。现有细粒度子命令（`steamlib`、`liveupdate`、`regen`、`visualize`）保持不变。

---

## 5. 与现有代码的关系

| 模块 | 改动 |
|------|------|
| `engine.py` | 无改动 |
| `aggregator.py` | 无改动 |
| `backup_ops.py` | 无改动 |
| `cli.py` | 编排逻辑迁移到调用 orchestrator |
| `cli-hmi/run.py` | 可替换为调用 orchestrator（非必须，demo 层） |

---

## 6. 实现顺序

```
Task 5: bootstrap.py    ← user_config 发现 + 数据库生成
Task 6: orchestrator.py ← 流水线调度
Task 7: CLI 适配        ← 改为调用 orchestrator
Task 8: 测试            ← bootstrap + orchestrator 测试
```

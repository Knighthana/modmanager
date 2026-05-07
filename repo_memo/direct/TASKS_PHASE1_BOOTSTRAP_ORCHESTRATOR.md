# Phase 1: Bootstrap & Orchestrator — 实现任务

> **2026-05-06 注**：本文档为 Phase 1 实现时的历史任务快照。
> 其中 `mapping_result.get("forest", [])` 在 P0 后已改为 `mapping_result.get("trees", [])`。
> 当前权威代码以 `orchestrator.py` 实际实现为准。

创建：2026-04-30
状态：已完成 ✅
前置设计：`repo_memo/direct/DESIGN_BOOTSTRAP_ORCHESTRATOR.md`
前置决策：`repo_memo/direct/QUESTIONS_BOOTSTRAP.md`（全部 8 个问题已决策 ✅）

---

## 前置阅读（必读）

实现前必须阅读以下文档：
1. `repo_memo/direct/DESIGN_BOOTSTRAP_ORCHESTRATOR.md`（完整设计）
2. `repo_memo/direct/QUESTIONS_BOOTSTRAP.md`（8 个决策记录）
3. `repo_memo/TASKLIST.md`（Phase 1 概述）
4. 现有源码（需了解的接口）：
   - `src/modmanager/engine.py` — `compute_mapping()`
   - `src/modmanager/backup_ops.py` — `run_differential_backup()`, `apply_final_mapping()`
   - `src/modmanager/rule_aggregator.py` — `aggregate()`
   - `src/modmanager/database_ops.py` — `discover_with_fallback()`
   - `src/modmanager/iojson.py` — `load_json_file()`, `write_json_file()`
   - `src/modmanager/cli.py` — 现有编排逻辑（将被迁移）

---

## Task 5: 创建 bootstrap.py

**文件**: `src/modmanager/bootstrap.py`（新建）

### 5.1 内部工具函数：`_detect_software_dir()`

```python
def _detect_software_dir() -> str:
    """从 __file__ 向上查找 pyproject.toml。

    找到则返回该目录（开发模式），否则返回 site-packages/modmanager/。
    """
```

**实现要点**：
- 从 `Path(__file__).resolve().parent` 开始向上遍历
- 在每个父目录检测是否包含 `pyproject.toml` 文件
- 找到则返回该父目录的绝对路径（posix 风格）
- 未找到（生产环境安装）则返回 `<site-packages>/modmanager/`
  - 获取方法：`Path(__file__).resolve().parent`（即 modmanager 包目录本身）
- 函数名以下划线开头，表示内部使用

### 5.2 `discover_user_config()`

```python
def discover_user_config(home_dir: str | None = None) -> dict:
    """搜索三级 user_config.json 并按层级合并。

    三级搜索链（后者覆盖前者）：
      1. ~/.config/kmm/user_config.json      （最低优先级）
      2. <软件本体目录>/user_config.json       （中优先级）
      3. $PWD/user_config.json                （最高优先级）

    合并规则：后者覆盖前者（dict 级别 shallow merge）。

    Args:
        home_dir: 用户主目录，None 时自动从环境变量获取
                        ($HOME / %USERPROFILE% / Path.home())

    Returns:
        合并后的 user_config 字典

    Raises:
        FileNotFoundError: 若三级搜索均未找到任何 user_config.json
    """
```

**实现要点**：
- `home_dir` 默认值：优先 `os.environ.get("HOME")`，其次 `os.environ.get("USERPROFILE")`，最后 `str(Path.home())`
- 软件本体目录通过 `_detect_software_dir()` 获取
- `$PWD` 通过 `os.getcwd()` 获取
- 使用 `iojson.load_json_file()` 加载 JSON
- 合并逻辑：对于第 1 层 merged = level1.copy()；第 2 层 merged.update(level2)；第 3 层 merged.update(level3)
- 若三层均未找到有效文件，抛出 `FileNotFoundError("No user_config.json found in any of the three search locations: ...")`
- 无效 JSON / 非 dict 类型 → 跳过该层（记录但不影响其他层）

### 5.3 `generate_database()`

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
            "manual" — 手动模式，paths 必须传入
                      （vdf 文件路径 或 steamapps 目录路径）
        paths: manual 模式下的路径列表
        working_pathstyle: "linux" | "windows"
        greedy_parsing: 是否放宽 mod 解析范围
        on_progress: 进度回调 (step, finished, total, message)
        cache_path: 若提供，优先从此路径加载缓存；
                    生成后写入此路径

    Returns:
        database 字典，格式兼容 engine.compute_mapping 的 database 输入

    Raises:
        ValueError: mode 不是 "auto" 或 "manual"
        ValueError: mode="manual" 但 paths 为空或未提供
    """
```

**实现要点**：

1. **缓存优先**：若 `cache_path` 存在且为非空文件，直接 `load_json_file(cache_path)` 返回
   - 返回前应验证基本结构（至少含 `"steamlib"` key 且为 list）

2. **mode="auto"**：
   - 调用 `database_ops.discover_with_fallback(working_pathstyle=working_pathstyle, greedy_parsing=greedy_parsing)`
   - 若 `on_progress` 存在，在调用前后发送进度：
     - 调用前：`on_progress("scan", 0, -1, "Discovering Steam libraries...")`
     - 调用后：`on_progress("scan", 1, 1, "Steam discovery complete")`

3. **mode="manual"**：
   - 将 `paths` 中的每条路径转换为 manual_override_steamlibs 格式：
     ```python
     manual_override_steamlibs = [
         {"path": p, "contains_libraryfolders_vdf": p.endswith(".vdf"), "game": []}
         for p in paths
     ]
     ```
   - 调用 `database_ops.discover_with_fallback(working_pathstyle=working_pathstyle, manual_override_steamlibs=manual_override_steamlibs, greedy_parsing=greedy_parsing)`
   - 若 `paths` 为 None 或空列表 → `raise ValueError("manual mode requires at least one path")`

4. **缓存写入**：生成成功后，若 `cache_path` 不为 None，`write_json_file(cache_path, database)`

5. **进度回调检查**：所有对 `on_progress` 的调用必须先检查 `on_progress is not None`

### 5.4 进度回调协议

`bootstrap.py` 中需要引用 `ProgressCallback` 类型。定义方式：

```python
from typing import Protocol

class ProgressCallback(Protocol):
    def __call__(self, step: str, finished: int, total: int, message: str = "") -> None:
        ...
```

由于 `bootstrap.py` 和 `orchestrator.py` 都需要这个类型，有两种方案：
- **方案 B（推荐）**：将 `ProgressCallback` 定义放在一个共享位置，两个模块都从那里导入
- **方案 A**：各自定义独立的 Protocol（Python Protocol 是 structural typing，只要签名一致就能互操作）

**决策：采用方案 A**。`bootstrap.py` 和 `orchestrator.py` 各自定义 `ProgressCallback` Protocol（内部使用），保持模块独立。Python 的 structural subtyping 保证互操作性。

---

## Task 6: 创建 orchestrator.py

**文件**: `src/modmanager/orchestrator.py`（新建）

### 6.1 数据结构

```python
from dataclasses import dataclass, field
from typing import Any, Protocol


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


@dataclass
class PipelineResult:
    """流水线执行结果"""
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    forest: list[dict[str, Any]] = field(default_factory=list)
    final_mapping: list[dict[str, Any]] = field(default_factory=list)
    mapping_result: dict[str, Any] = field(default_factory=dict)
    backup_result: dict[str, Any] | None = None
    apply_result: dict[str, Any] | None = None
```

### 6.2 `compute()`

```python
def compute(
    database: dict,
    kmm_rule_paths: list[str],
    user_config_path: str,
    *,
    action_orders: dict[str, int] | None = None,
    branch_decisions: dict[str, str] | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """聚合规则 → 计算映射。

    步骤：
      1. 调用 rule_aggregator.aggregate() 聚合规则
      2. 调用 engine.compute_mapping() 计算映射

    返回 PipelineResult（backup_result 和 apply_result 为 None）。
    """
```

**实现要点**：
- 聚合阶段：
  ```python
  if on_progress:
      on_progress("aggregate", 0, 1, "Aggregating rules...")
  aggregated, agg_errors, agg_warnings = aggregate(
      kmm_rule_paths, user_config_path,
      action_orders=action_orders
  )
  if on_progress:
      on_progress("aggregate", 1, 1, "Rule aggregation complete")
  ```
- 若聚合失败（`aggregated is None` 或 `agg_errors` 非空）→ 返回失败的 `PipelineResult(ok=False, errors=agg_errors, warnings=agg_warnings)`
- 计算阶段：
  ```python
  if on_progress:
      on_progress("compute", 0, 1, "Computing mapping...")
  mapping_result = compute_mapping(
      aggregated_rule_set=aggregated,
      database=database,
      branch_decisions=branch_decisions or {},
  )
  if on_progress:
      on_progress("compute", 1, 1, "Mapping computation complete")
  ```
- 组装 `PipelineResult`：
  - `ok = not mapping_result.get("errors")`
  - `errors = mapping_result.get("errors", [])`
  - `warnings = agg_warnings + mapping_result.get("warnings", [])`
  - `forest = mapping_result.get("forest", [])`
  - `final_mapping = mapping_result.get("final_mapping", [])`
  - `mapping_result = mapping_result`
  - `backup_result = None`
  - `apply_result = None`

### 6.3 `backup()`

```python
def backup(
    mapping_result: dict[str, Any],
    backup_dir: str,
    *,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """对 final_mapping 中的文件执行差异备份。

    Args:
        mapping_result: compute_mapping 的原始输出
        backup_dir: 备份目录路径
        on_progress: 进度回调

    Returns:
        run_differential_backup 的返回结果字典
    """
```

**实现要点**：
- 从 `mapping_result` 中提取 `final_mapping`
- 提取 `files_to_backup = [entry["path"] for entry in final_mapping if entry.get("path")]`
- 若 `files_to_backup` 为空 → 返回 `{"ok": True, "backed_up": [], "skipped": [], "errors": []}`
- 调用 `run_differential_backup(backup_dir, files_to_backup)`，用 `on_progress` 传递进度

### 6.4 `apply()`

```python
def apply(
    final_mapping: list[dict[str, Any]],
    backup_dir: str,
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """执行 final_mapping 的磁盘替换。

    Args:
        final_mapping: compute_mapping 产出的 final_mapping 列表
        backup_dir: 备份目录路径（gate 检查用）
        dry_run: True 则仅检查 gate，不执行文件操作
        on_progress: 进度回调

    Returns:
        apply_final_mapping 的返回结果字典
    """
```

**实现要点**：
- 调用 `apply_final_mapping(final_mapping, backup_dir, dry_run=dry_run)`
- 用 `on_progress` 在前后通知

### 6.5 `run()` — 全流水线

```python
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

    若 compute() 失败（PipelineResult.ok == False），
    停止后续步骤，直接返回。

    若 backup() 失败（result["ok"] == False），
    停止后续步骤，将 backup_result 组装到 PipelineResult 中返回。
    """
```

**实现要点**：
1. 调用 `compute(database, kmm_rule_paths, user_config_path, action_orders=action_orders, branch_decisions=branch_decisions, on_progress=on_progress)`
2. 若 `compute_result.ok == False` → 直接返回 `compute_result`
3. 调用 `backup(compute_result.mapping_result, backup_dir, on_progress=on_progress)`
4. 若 `backup_result.get("ok") == False` → 组装 `PipelineResult`：
   - `ok=False`，`errors` 合并 backup_result 的 errors
   - 保留 compute 阶段的 forest、final_mapping、mapping_result
   - 设置 `backup_result`
5. 调用 `apply(compute_result.final_mapping, backup_dir, dry_run=dry_run, on_progress=on_progress)`
6. 组装最终 `PipelineResult`：
   - `ok = not (compute_errors or backup_errors or apply_errors)`
   - `errors` / `warnings` 合并所有阶段的
   - 保留所有中间结果

---

## Task 7: CLI 适配

**文件**: `src/modmanager/cli.py`（修改）

### 7.1 新增公共函数 `_get_default_user_config_path()`

```python
def _get_default_user_config_path() -> str:
    """返回推荐的 user_config.json 路径：
    ~/.config/kmm/user_config.json
    """
    import os
    from pathlib import Path
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or str(Path.home())
    return str(Path(home) / ".config" / "kmm" / "user_config.json")
```

用途：供 CLI 命令中需要 `user_config_path` 时使用（仅在显式传入参数为空时 fallback）。

### 7.2 修改 `_handle_backup()`

**当前逻辑**（L215–246）：
1. 加载 aggregated_rule_set、database、decisions
2. 调用 compute_mapping
3. 提取 final_mapping
4. 调用 run_differential_backup

**新逻辑**：改为调用 orchestrator
```python
def _handle_backup(args: argparse.Namespace) -> int:
    from .orchestrator import backup as orch_backup
    try:
        aggregated_rule_set = load_json_file(args.aggregated_rule_set)
        database = load_json_file(args.database)
        decisions = load_json_file(args.decisions) if args.decisions else {}
    except Exception as exc:
        return _emit_error(f"failed to load inputs: {exc}")

    try:
        mapping_result = compute_mapping(
            aggregated_rule_set=aggregated_rule_set,
            database=database,
            branch_decisions=decisions,
        )
    except Exception as exc:
        return _emit_error(f"compute_mapping failed: {exc}")

    if mapping_result.get("errors"):
        return _emit_error(f"mapping has errors: {mapping_result['errors']}")

    final_mapping = mapping_result.get("final_mapping", [])
    if not final_mapping:
        return _emit_error("no final_mapping produced; resolve branch conflicts first")

    result = orch_backup(mapping_result, args.backup_dir)
    _print_or_write(result, args.out)
    return 0 if result.get("ok") else 2
```

**注意**：保留原有的 load → compute_mapping → 检查 final_mapping → 调 orchestrator.backup() 的结构。实际上 `_handle_backup()` 的改动可以最小化——已经正确地把 compute_mapping 的结果传给备份逻辑。但因为 `orchestrator.backup()` 接受 `mapping_result`（而非 `final_mapping`），需要在调用时改用 orchestrator 的函数签名。

实际上仔细看当前的 `_handle_backup()`，它已经做了 compute_mapping + 提取 files + run_differential_backup。最小改动：**仅将 `run_differential_backup` 的直接调用替换为 `orchestrator.backup(mapping_result, backup_dir)`**。这样在 orchestrator.backup() 内部处理文件提取。

### 7.3 修改 `_handle_apply()`

同理，**仅将 `apply_final_mapping` 的直接调用替换为 `orchestrator.apply(final_mapping, backup_dir, dry_run=dry_run)`**。

### 7.4 修改 `main()` 中的 compute 模式

**当前 L365–396**：解析参数，加载文件，调用 `compute_mapping`，输出结果。

**新逻辑**：可以保持不变（直接调用 compute_mapping 是最简单的纯 compute 路径），也可以改为调用 `orchestrator.compute()`。**决策：保持现有逻辑不变**，因为：
- 纯 compute 模式下没有规则聚合步骤（aggregated_rule_set 是 CLI 直接传入的）
- 无需引入 orchestrator 的额外复杂性
- 若将来需要，可以再迁移

### 7.5 不需要改动的部分

以下子命令**保持不变**：
- `steamlib` 系列子命令
- `liveupdate` 子命令
- `regen` 子命令
- `restore` 子命令
- `visualize` 子命令

### 7.6 更详细的 CLI 讨论（可选，非必须）

设计文档提到 CLI 可变为薄壳（直接调用 orchestrator）。当前最小改动方案是先确保 orchestrator API 可用，CLI 内部可以后续再精简。当前阶段：
- `_handle_backup()` 中之前是直接调用 `run_differential_backup`，现在改为通过 `orchestrator.backup()` 
- `_handle_apply()` 中之前是直接调用 `apply_final_mapping`，现在改为通过 `orchestrator.apply()`

这样既让 orchestrator 有了实际使用场景，改动也最小。

---

## Task 8: 测试

### 8.1 新增 `tests/test_bootstrap.py`

**测试用例**：

1. **`test_detect_software_dir_returns_string`**
   - 调用 `_detect_software_dir()`，验证返回非空字符串
   - 验证返回路径是绝对路径
   - 验证返回路径以 `/modmanager` 结尾（或包含 `pyproject.toml` 的父目录）

2. **`test_discover_user_config_no_files_raises`**
   - 传入不存在的 `home_dir`，验证抛出 `FileNotFoundError`
   - 使用 `pytest.raises(FileNotFoundError)`

3. **`test_discover_user_config_single_level`**
   - 创建临时目录 + 临时 `user_config.json`
   - 验证 discover_user_config 能正确读取

4. **`test_discover_user_config_multi_level_merge`**
   - 创建三级临时目录结构（模拟 ~/.config/kmm/、软件本体目录/、$PWD/）
   - 放置不同层级的 user_config.json
   - 验证合并结果：高优先级覆盖低优先级

5. **`test_discover_user_config_invalid_json_skipped`**
   - 其中某一层的 JSON 文件内容无效
   - 验证该层被跳过，不影响其他层

6. **`test_generate_database_invalid_mode`**
   - `mode="invalid"` → `ValueError`

7. **`test_generate_database_manual_empty_paths`**
   - `mode="manual"`, `paths=[]` → `ValueError`

8. **`test_generate_database_cache_hit`**
   - 创建临时 cache 文件，传入 `cache_path`
   - 验证返回内容与缓存文件一致

### 8.2 新增 `tests/test_orchestrator.py`

**测试用例**：

1. **`test_pipeline_result_defaults`**
   - 构造空的 PipelineResult，验证默认字段值正确

2. **`test_compute_success_path`**
   - 使用有效的 database + kmm_rule_paths + user_config 构造参数
   - 验证返回的 PipelineResult.ok == True
   - 验证 final_mapping 和 forest 非空

3. **`test_compute_aggregation_failure`**
   - 传入无效的 kmm_rule_paths
   - 验证 PipelineResult.ok == False
   - 验证 errors 包含聚合相关的错误

4. **`test_backup_no_files`**
   - mapping_result 中 final_mapping 为空
   - 验证返回的 result["ok"] == True, "backed_up" 为空

5. **`test_run_full_pipeline`**
   - 端到端测试（使用可用的测试夹具）
   - 验证 PipelineResult 的 ok 和结果字段

6. **`test_progress_callback_invoked`**
   - 传入 mock on_progress
   - 验证 compute/backup/apply 阶段回调被调用

### 8.3 修改 `tests/test_cli_database_ops.py`（如需）

检查并确保 CLI 测试适配新的 orchestrator 调用方式（预期不需要改动，因为 CLI 的 `_handle_backup` 和 `_handle_apply` 行为不变）。

---

## 执行顺序

```
Task 5 (bootstrap.py)  ← 先做，独立无依赖
Task 6 (orchestrator.py) ← 可与 Task 5 并行，但依赖 bootstrap 完成 ProgressCallback 定义
Task 7 (CLI 适配)       ← 依赖 Task 6 完成
Task 8 (测试)           ← 依赖 Task 5/6/7 完成
```

---

## 验收标准

1. `python -m pytest tests/test_bootstrap.py -v` 全量通过
2. `python -m pytest tests/test_orchestrator.py -v` 全量通过
3. `python -m pytest tests/ -v` 全量通过（不破坏已有 243+ 测试）
4. `python -m modmanager.cli backup --help` 和 `apply --help` 正常显示
5. orchestrator 的三个分批接口 (`compute` / `backup` / `apply`) 与 `run` 全流水线接口行为一致
6. bootstrap 的 `discover_user_config` 正确完成三级搜索合并

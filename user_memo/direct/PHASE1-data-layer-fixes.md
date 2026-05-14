# Phase 1 — 数据层修正

> Status: plan
> Authority: arch
> Created: 2026-05-14
> Source: `work_memo/2026-05-14_decisions.md`（vFinal 方案 B）
> 原则：自底向上。先改数据层，不改 API 和前端。改完跑全量 Python test。

---

## Task 1.1: `bootstrap.py` — user_config 搜索改为单级

### 当前行为
`discover_user_config()` 使用三级搜索合并（`~/.config/kmm/` → `<software_dir>/` → `$PWD/`）。

### 目标行为
单级唯一搜索 + first_use 机制：

```
搜索 ~/.config/kmm/user_config.json (Linux) 或 %appdata%/kmm/user_config.json (Windows)
  ├── 文件存在 → 加载返回，first_use = false
  └── 文件不存在 → 创建空默认配置（含 databases: {"default": {"path": "平台默认"}}），first_use = true
```

### 修改文件
`src/modmanager/bootstrap.py`

### 具体改动
1. 改 `discover_user_config()`:
   - 删除 tier2（软件目录）和 tier3（$PWD）的搜索
   - 只搜索平台默认位置
   - 文件不存在时：创建空配置，写入默认 databases 对象
   - 返回 `{config, source_path, first_use}` 或字典（与现有调用方兼容）
   - 保留 `home_dir` 参数

2. 默认 databases 对象：
```python
DEFAULT_DATABASES = {
    "default": {"path": normalize_posix(str(Path(home_dir) / ".local" / "share" / "kmm" / "database.json"))}
}
```

---

## Task 1.2: `bootstrap.py` — `generate_database()` 从 user_config.databases 获取路径

### 当前行为
`generate_database()` 接收 `cache_path` 参数，或直接扫描不指定输出路径。

### 目标行为
- 接收 `database_name?: string`（可选，默认 `"default"`）
- 内部加载 user_config → 查 `databases[database_name].path` → 确定读/写路径
- 删除 `cache_path` 参数
- 缓存逻辑简化：按确定的 path 判断是否需要重新扫描

### 具体改动
```python
def generate_database(
    mode: str,
    *,
    paths: list[str] | None = None,
    working_pathstyle: str = "linux",
    greedy_parsing: bool = False,
    on_progress: ProgressCallback | None = None,
    database_name: str = "default",     # 新增
) -> dict:
    # 内部：
    config = discover_user_config()
    db_path = config.get("databases", {}).get(database_name, {}).get("path")
    if not db_path:
        raise ValueError(f"database '{database_name}' not found in user_config.databases")
    # ... 扫描逻辑，完成后写回 db_path
```

删除旧 `cache_path` 参数的所有逻辑。

---

## Task 1.3: `workspace.py` — 归档

### 操作
- 将 `src/modmanager/workspace.py` 移动到 `repo_memo/archive/workspace.py`（代码归档，不从 src/ 删除——等 API 层改造后再删引用）
- 或在 Phase 2 删除 `routes/workspace.py` 时一并处理

**当前 Phase 1 暂不删除**——检查 orchestrator 和其他模块是否有 import workspace 的引用。若有引用但逻辑需要改（改为从请求参数获取 decisions），则标记 TODO。

### 检查
```bash
grep -rn "from modmanager.workspace import\|from modmanager import workspace" src/
```
若有引用，记录下来。在 Phase 2 一并处理。

---

## Task 1.4: `rule_aggregator.py` — 删除 `user_config_path` 参数

### 当前签名
```python
def aggregate(
    kmm_rule_paths: list[str],
    user_config_path: str,    # ← 删除
    *,
    action_orders: ... = None,
    sidecar_refs: ... = None,
    output_path: str | None = None,
) -> tuple[...]
```

### 目标签名
```python
def aggregate(
    kmm_rule_paths: list[str],
    *,
    action_orders: dict[str, int] | None = None,
    sidecar_refs: dict[...] | None = None,
    output_path: str | None = None,
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
```

### 具体改动
1. 删 `user_config_path` 参数
2. 删 `_load_user_config()` 调用
3. 删 `E_USER_CONFIG_LOAD_FAILED` 错误码
4. 删聚合流程中"加载 user_config.json"步骤
5. 检查所有调用方（CLI、routes/rules.py、orchestrator）→ 传参中删除 `user_config_path`

---

## Task 1.5: `orchestrator.py` — 确认签名

### 当前签名
```python
def compute(
    database: dict,
    kmm_rule_paths: list[str] | None = None,
    user_config_path: str = "",
    *,
    aggregated_rule_path: str | None = None,
    action_orders: dict[str, int] | None = None,
    branch_decisions: dict[str, str] | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
```

### 目标签名
```python
def compute(
    database: dict,
    *,
    kmm_rule_paths: list[str] | None = None,
    aggregated_rule_path: str | None = None,
    action_orders: dict[str, int] | None = None,
    branch_decisions: dict[str, str] | None = None,
    managed_entries: dict | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
```

### 具体改动
1. `database` 保留为 `dict`（调用方已加载好书序）
2. 删除 `user_config_path` 参数（orchestrator 不管）
3. 新增 `managed_entries: dict | None = None` 参数
4. `_apply_managed_filter(database, managed_entries)` 逻辑保留——它已经存在
5. `run()` 签名同步修改

---

## Task 1.6: 检查 `rules.py` 中的 aggregate 调用

`src/modmanager_web/routes/rules.py` 第 130 行调用 aggregate 时传了 `user_config_path` 和 `output_path`：
```python
result, errors, warnings = rule_aggregate(
    req.paths,
    user_config_path,
    output_path=output_path,
)
```

### 需要改
- 删 `user_config_path` 参数
- `output_path` 改为从 user_config 获取（`user_config.aggregated_ruleset_output_path`）
- 不从 workspace 读 `aggregated_rule_path`

当前 Phase 1 只检查和记录问题——不改（属于 API 层 Phase 2）。

---

## 执行顺序

1. Task 1.1 — bootstrap user_config 单级搜索
2. Task 1.2 — bootstrap generate_database 改用 databases
3. Task 1.3 — 检查 workspace.py 引用情况
4. Task 1.4 — rule_aggregator 删 user_config_path
5. Task 1.5 — orchestrator 签名确认
6. Task 1.6 — 检查 rules.py aggregate 调用

---

## 验收

```bash
cd /home/knighthana/workspace/modmanager_cli
python -m pytest tests/ -x -q
```

全量 Python test 通过。任何 failing test 需要对应修正测试代码（测试也应该不再传 user_config_path、不再依赖三级搜索等旧行为）。

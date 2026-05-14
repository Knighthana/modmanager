# Phase 2 — API 层修正

> Status: plan
> Authority: arch
> Created: 2026-05-14
> Source: `work_memo/2026-05-14_decisions.md`（vFinal 方案 B）+ Phase 1 产物
> 前置：Phase 1 已完成。全部 Python test 通过。

---

## Task 2.1: `schemas.py` — 全面更新

### 文件
`src/modmanager_web/schemas.py`

### 具体改动

| Schema | 改什么 |
|--------|--------|
| `GenerateDatabaseRequest` | 删 `cache_path`；加 `database_name: str = "default"` |
| `LoadDatabaseRequest` | 重命名为 `ReadDatabaseRequest`。删 `path`；加 `database_name: str = "default"` |
| `SaveDatabaseRequest` | 删 `output_path`；加 `database_name: str = "default"` |
| `ComputeRequest` | `database: Any` → 删。`user_config_path: str` → 删。加 `database_name: str = "default"`。加 `managed_entries: dict \| None = None`。加 `branch_decisions: dict[str, str] \| None = None` |
| `RunRequest` | 同上 + 保留 `backup_dir`、`dry_run` |
| `BackupRequest` | 删 `database`、`user_config_path` |
| `ApplyRequest` | 删 `database`、`user_config_path` |
| `SaveInputsRequest` | **删除整个 class** |
| `SaveDecisionsRequest` | **删除整个 class** |
| `SaveResultsRequest` | **删除整个 class** |
| `SaveConfigRequest` | 删 `output_path` |

### 注意
删除 `SaveInputsRequest` / `SaveDecisionsRequest` / `SaveResultsRequest` 后，相关的 import 引用在 `routes/workspace.py` 中——Task 2.2 会删整个文件。

---

## Task 2.2: `routes/workspace.py` — 删除

### 操作
删除 `src/modmanager_web/routes/workspace.py` 整个文件。

Phase 1 Task 1.3 已确认引用情况：此文件被 `app.py` 注册，另有两处 lazy import 在 `routes/rules.py`。

---

## Task 2.3: `routes/database.py` — 端点更新

### 文件
`src/modmanager_web/routes/database.py`

### 具体改动

1. **`POST /generate`**: 
   - `cache_path=req.cache_path` → 删。改用 `database_name=req.database_name`
   - `generate_database(...)` 调用更新（已不需要传 cache_path）

2. **`POST /load`** → 改为 **`POST /read`**:
   - 函数名从 `load_database` 改为 `read_database`
   - 不接收 `path` 参数。改为接收 `database_name`
   - 内部：查 user_config.databases[database_name].path → `load_json_file(resolved)`

3. **`POST /save`**:
   - 不再接收 `output_path`。改为接收 `database_name`
   - `write_json_file(...)` 的路径从 user_config.databases[database_name].path 获取

### 新增工具函数（可放在此文件或单独 utils）
```python
def _resolve_database_path(database_name: str, user_config: dict) -> str:
    db = user_config.get("databases", {}).get(database_name)
    if not db:
        raise ValueError(f"database '{database_name}' not found in user_config.databases")
    return db["path"]
```

---

## Task 2.4: `routes/pipeline.py` — compute/run/backup/apply 更新

### 文件
`src/modmanager_web/routes/pipeline.py`

### 具体改动

1. **`POST /compute`** (`pipeline_compute`):
   - 删除 `database: Any` 的手动加载逻辑（第 47-51 行的 `if isinstance(db, str): resolve...`）
   - 改为：从 `req.database_name` 获取路径 → 加载 database dict
   - 传入 orchestrator 时：`managed_entries=req.managed_entries`、`branch_decisions=req.branch_decisions`
   - 删除 `user_config_path` 相关逻辑

2. **`POST /run`** (`pipeline_run`):
   - 同上

3. **`POST /backup`** (`pipeline_backup`):
   - 删除 `req.database` 和 `req.user_config_path` 相关逻辑
   - backup_dir 的自动推导改为内部从 user_config 获取

4. **`POST /apply`** (`pipeline_apply`):
   - 同上

### 注意
backup/apply 的 `build_backup_dir()` 依赖 `database` 和 `user_config`。之前是从请求体来的。改为从 user_config（调用 `_discover_or_load_config()`）获取。

---

## Task 2.5: `routes/rules.py` — 解除 workspace 依赖

### 文件
`src/modmanager_web/routes/rules.py`

### Phase 1 Task 1.6 发现的问题

1. **`/aggregate`**（第 112-127 行）：从 workspace 读 `aggregated_rule_path` 和 `user_config_path`
   - 改为：从 user_config 读 `aggregated_ruleset_output_path`
   - 不再传 `user_config_path` 给 aggregate()

2. **`/affected-entries`**（第 169-180 行）：从 workspace 读 `database_path`
   - 改为：从 user_config.databases 获取路径
   - 新增 `database_name?: string` 参数（默认 "default"）

---

## Task 2.6: `routes/config.py` — 删除 output_path

### 文件
`src/modmanager_web/routes/config.py`

### 具体改动
`POST /api/config/save`:
- 删除 `output_path` 相关逻辑
- 改为写入平台默认位置（`~/.config/kmm/user_config.json`）
- 调用 `_discover_or_create_config()` 获取目标路径

---

## Task 2.7: `app.py` — 注销 workspace 路由

### 文件
`src/modmanager_web/app.py`

### 具体改动
- 删除 `from .routes import workspace` 
- 删除 `app.include_router(workspace.router, ...)` 或类似注册代码

---

## 执行顺序

1. Task 2.1 — schemas.py
2. Task 2.2 — 删 routes/workspace.py
3. Task 2.7 — app.py 注销路由（防止 import 报错）
4. Task 2.3 — routes/database.py
5. Task 2.4 — routes/pipeline.py
6. Task 2.5 — routes/rules.py
7. Task 2.6 — routes/config.py

---

## 验收

```bash
cd /home/knighthana/workspace/modmanager_cli
python -m pytest tests/ -x -q
```

全量 Python test 通过。注意测试文件 `test_web_api.py` 中有大量 workspace 端点测试——这些测试需要同步删除或改为测试正确参数。

# PLAN — 引擎函数与工作区函数职责分离

> Last-Updated: 2026-05-18

## 目标

将 `orchestrator.py` 按 KISS 原则分离为两层：

- **引擎函数**（`compute` / `backup` / `apply` / `restore` / `run`）：接收消费品 `(final_mapping, database, user_config, flags)`，完成引擎职责。需要 backup_dir 时**自己调 `build_backup_dirs`**，不依赖外部传入。
- **工作区函数**（`*_ws`）：唯一职责——把"工作区"翻译成消费品 → 委托引擎函数。不传 backup_dirs，不代引擎做决策。

## 架构原则

1. **backup_dir 计算外包**：`backup_dir_builder.build_backup_dirs` 是唯一计算源。任何需要 backup_dir 的代码调它获取。
2. **引擎不接收 backup_dirs 参数**：签名统一为 `(final_mapping, database, user_config, flags, on_progress)`。
3. **`_ws` 不传 backup_dirs**：只翻译工作区语境为消费品，引擎自己算。
4. **database 不变假设**：工作区创建时与 database 强绑定；若 database 变了，那是另一个任务。
5. **不存在 MUST same backup_dir**：用户可通过修改 prefix 控制备份目录位置。

## 当前问题

| 函数 | 问题 |
|------|------|
| `backup()` | 签名含 `backup_dirs: dict`——应由引擎内部计算 |
| `apply()` | 签名用单 `backup_dir: str`；引擎职责（gate check + 循环）在 `apply_ws` 中 |
| `apply_ws()` | 越权——做了引擎该做的事 |
| `restore` | 引擎函数不存在 |
| `restore_ws` | 不存在 |
| `run()` / `run_ws()` | 传 `backup_dir: str`，未适配 |

## 改造方案

### 引擎函数统一签名

所有引擎函数接收消费品 + 标志位：

```
compute(database, aggregated_rule_set, managed_entries, branch_decisions, action_orders, on_progress)
  → 不需要 backup_dir

backup(final_mapping, database, user_config, *, dry_run, on_progress)
  → 内部调 build_backup_dirs → 遍历 dirs → run_differential_backup

apply(final_mapping, database, user_config, *, dry_run, on_progress)
  → 内部调 build_backup_dirs → 遍历 dirs → gate check → apply_final_mapping

restore(final_mapping, database, user_config, *, force, on_progress)
  → 内部调 build_backup_dirs → 遍历 dirs → 读 backupinfo → 比对/覆盖

run(database, aggregated_rule_set, managed_entries, branch_decisions, user_config, *, dry_run, on_progress)
  → compute → backup → apply（链式调用引擎函数）
```

### 工作区函数统一模式

```
compute_ws(workspace_id, on_progress)
  → 加载 aggregated_rule_set + decisions + database
  → compute(database, aggregated_rule_set, managed_entries, branch_decisions, on_progress)
  → 写 mapping + SVG 回工作区

backup_ws(workspace_id, *, dry_run, on_progress)
  → 加载 final_mapping + database + user_config
  → backup(final_mapping, database, user_config, dry_run=dry_run, on_progress=on_progress)

apply_ws(workspace_id, *, dry_run, on_progress)
  → 加载 final_mapping + database + user_config
  → apply(final_mapping, database, user_config, dry_run=dry_run, on_progress=on_progress)

restore_ws(workspace_id, *, force, on_progress)
  → 加载 final_mapping + database + user_config
  → restore(final_mapping, database, user_config, force=force, on_progress=on_progress)

run_ws(workspace_id, *, dry_run, on_progress)
  → 加载 aggregated_rule_set + decisions + database + user_config + final_mapping
  → run(database, aggregated_rule_set, managed_entries, branch_decisions, user_config, dry_run=dry_run, on_progress=on_progress)
```

### `backup()` 引擎函数（重写）

```python
def backup(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    backup_dirs, warnings = build_backup_dirs(final_mapping, database, user_config)
    # 遍历 backup_dirs → run_differential_backup → 聚合
```

### `apply()` 引擎函数（重写）

```python
def apply(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    backup_dirs, warnings = build_backup_dirs(final_mapping, database, user_config)
    # 遍历 backup_dirs → gate check → apply_final_mapping → 聚合
```

### `restore()` 引擎函数（新增）

```python
def restore(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
    *,
    force: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    backup_dirs, warnings = build_backup_dirs(final_mapping, database, user_config)
    # 遍历 backup_dirs：
    #   读 backupinfo.json → filefoldertree
    #   对组内每个文件：
    #     force=OFF → 算 HASH 比对 → 相同跳过 / 不同回写
    #     force=ON  → 查有无 → 有则回写 / 无则警告
```

### `run()` 引擎函数（重写）

```python
def run(
    database: dict[str, Any],
    aggregated_rule_set: dict[str, Any],
    managed_entries: dict | None,
    branch_decisions: dict[str, str] | None,
    user_config: dict[str, Any],
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    # compute → backup → apply（纯链式调用）
```

## 与现有文档对比

| 文档 | 需要更新 |
|------|---------|
| `DESIGN_ORCHESTRATOR.md` | 全部引擎函数签名重写（`backup_dirs` 参数移除，增加 `database`/`user_config`）；新增 `restore()` / `restore_ws()` |
| `DESIGN_BACKUP.md` §6 | 签名更新 |
| `DESIGN_REST_API.md` | restore 端点 schema：`dry_run` → `force` |
| `schemas.py` | `WorkspaceRestoreRequest`: `force: bool = False` |
| 前端 | restore 按钮/提示文案调整 |

## 实施顺序

1. 重写 `backup()` 引擎函数（`backup_dirs` 参数移除，内部调 `build_backup_dirs`）
2. 重写 `apply()` 引擎函数（同上 + gate check 下沉）
3. 新增 `restore()` 引擎函数
4. 重写 `run()` 引擎函数
5. 简化 `backup_ws()` / `apply_ws()` / `run_ws()`（退化为翻译 + 委托）
6. 新增 `restore_ws()`
7. 更新 `WorkspaceRestoreRequest` schema（`dry_run` → `force`）
8. 更新 `routes/workspace.py` restore 端点 + 前端
9. 验证全部导入 + 编译
10. 更新文档签名
11. 提交

---

## bakprefix → baksuffix 迁移

### 命名格式变更

| 范围 | 旧 | 新 |
|------|----|----|
| 备份目录名 | `kmmbackup_270150_hex/` | `270150.hex.kmmbackup/` |
| contentid 目录 | `kmmbackup_2606099273_hex/` | `2606099273.hex.kmmbackup/` |
| user_config 字段 | `bakprefix: "kmmbackup_"` | `baksuffix: "kmmbackup"` |
| 硬编码防护 | `startswith("kmmbackup_")` | `endswith(".kmmbackup")` |

### 涉及文件

| 文件 | 改动 |
|------|------|
| `backup_ops.py` | `_HARDCODED_BACKUP_SKIP_PREFIX` → `_HARDCODED_BACKUP_SKIP_SUFFIX`；三处 `startswith` → `endswith` |
| `backup_dir_builder.py` | `bakprefix` → `baksuffix`；命名拼接改为后缀格式 |
| `orchestrator.py` | 硬编码 `{"bakprefix": "kmmbackup_"}` → `{"baksuffix": "kmmbackup"}` |
| `workspacemanager.py` | 无直接引用，下游通过 user_config 获取 |
| `DESIGN_BACKUP.md` | 全部 `bakprefix` → `baksuffix` |
| `DESIGN_GUI.md` | 同上 |
| 前端 `zh-CN.ts` | locale 无此字段 |
| 其他文档 | 搜索 `bakprefix\|kmmbackup_\|前缀` 逐一清理 |

### bakignore 规则改造

- 引入 `gitignore-parser`（`pip install gitignore-parser`），加入 `pyproject.toml` 依赖
- `load_bakignore_rules` 重写为活代码：接收 `user_config.bakignore` + `backup_dir/.kmmbakignore` 路径列表，用 gitignore-parser 迭代解析
- 备份时：读取每个 contentid 源目录中的 `.kmmbakignore`，传给 parser 用于忽略判断，**同时将 `.kmmbakignore` 文件本身拷贝进 backup_dir**
- 应用时：将 backup_dir 中的 `.kmmbakignore` 覆盖回源目录对应位置
- user_config 的备份忽略模式仅用于根目录检查根目录的点分后缀目录名称，防循环备份；引擎内部硬编码 `.kmmbackup` 后缀不依赖 user_config

### 全项目"前缀"清理

非日志文件中所有 `bakprefix` / `kmmbackup_` / `backup_prefix` 字面替换为对应后缀格式。日志（`repo_logs/`、`user_memo/archive/`）不动。

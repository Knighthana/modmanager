# PLAN — prep 原语拆分 + ignore 下传阻断

> 创建：2026-05-21 by arch
> 状态：completed — 全部 4 项差距已修复

## 目标

1. 从 `backup_ops.py` 中拆分出 `prep.py`（创建 backup_dir 目录结构 + 建初始 tree + 写 `backupinfo.json`）
2. backup / restore / apply 彻底失去「知道 ignore」的必要性——通过函数签名隔离，不接收 Plan 对象
3. `FileOpsPlan` 保留 `ignore_rules` 字段作为 Plan 资产，primitive 无法访问

## 新模块

### `src/modmanager/prep.py`

**职责**：创建 backup_dir 目录结构 + 扫描源目录建初始 tree + 写入 `backupinfo.json`。受 Planner 调用，知道 ignore 语义。

**接口**：

```python
def prep_backup_dir(
    backup_dir: str,
    ignore_rules: IgnoreRuleSet,
    *,
    on_progress=None,
) -> dict:
    """创建 backup_dir 目录结构，扫描源目录建初始 tree，写入 backupinfo.json。

    Args:
        backup_dir: 目标备份目录路径
        ignore_rules: Planner 收集的 IgnoreRuleSet
        on_progress: 可选的进度回调

    Returns:
        初始 backupinfo dict（tree 中所有文件: isbackuped=false,
        hashtype="invalid", hashvalue="0"）
    """
```

内部行为：
1. `source_root = Path(backup_dir).parent`
2. 创建 backup_dir 目录
3. 迭代扫描 source_root 中所有目录和文件（应用 ignore_rules 过滤）
4. 构造 tree dict——每个 FileNode: `isbackuped=false`, `hashtype="invalid"`, `hashvalue="0"`
5. 构造完整 backupinfo dict（含 `schema_namespace`, `snapshot_time`, `last_modified_time`, `schema_version`, `tree`）
6. 写入 `backup_dir/backupinfo.json`
7. 返回 backupinfo dict

## 变更模块

### `orchestrator/planner_fileops.py`

**FileOpsPlan** 变化：
- 保留 `ignore_rules` 字段——Plan 资产，Planner 持有，prep 消费。primitive 通过函数签名隔离无法访问
- 新增 `needs_tree_build: bool` 字段

**plan_fileops** 变化：
- 收集 ignore_rules → 存入 `FileOpsPlan.ignore_rules`
- 调用 `build_backup_dirs` 后，对每个 backup_dir 检查是否需要建树
- 建树判断逻辑：`backup_dir` 目录不存在 **或** `backupinfo.json` 中的 tree 为空/不完整 → `needs_tree_build=True`

### `orchestrator/__init__.py` — `_dispatch_fileops`

新调度逻辑（intent=BACKUP）：

```python
if plan.needs_tree_build:
    prep_backup_dir(backup_dir, plan.ignore_rules)
# 然后执行 backup
_execute_backup_plan(entries, tree, plan.dry_run, on_progress)
```

### `src/modmanager/backup_ops.py`

删除：
- `build_dir_tree_with_hashes`（移到 prep.py）
- `init_backup_dir`（移到 prep.py）
- `finalize_backup_dir`（移到 prep.py）
- 所有 ignore 相关 import

保留：
- `run_differential_backup`——修改为接收预建的 tree + 预过滤的 entries，按 §六 流程执行
- **新增**：`.kmmignore` 文件复制逻辑——从源目录的祖先目录中收集 `.kmmignore` 文件，复制进 backup_dir 的对应位置

backup 对 tree 只有**更新状态**的方法：
- 读树（从 Plan 或从 `backupinfo.json`）
- 查结点是否存在 → 不存在则记录 `W_BACKUP_NODE_NOT_IN_TREE`，不改树
- 更新 `hashtype` / `hashvalue` / `isbackuped`（仅 false→true 方向，拷贝成功后）
- **不新增结点、不删除结点、不改变树结构**

### `src/modmanager/restore_ops.py`

- 接收预过滤的 entries + tree（由 Planner 提供）
- 不需要 ignore_rules
- **新增**：`.kmmignore` 文件还原逻辑——从 backup_dir 中收集 `.kmmignore` 文件，复制回源目录的对应位置
- 只读树——不修改任何结点

### `src/modmanager/apply_ops.py`

- 不需要任何变更——已经不知道 ignore，不管树

## ignore_rules 的生命周期

`plan_fileops()` 收集 ignore_rules → 存入 `FileOpsPlan.ignore_rules`。`_dispatch_fileops` 从 `plan.ignore_rules` 读取，传给 prep（如果建树）。primitive 函数不接收 Plan 对象，无法访问。

```
_dispatch_fileops:
  1. plan_fileops() → Plan（含 ignore_rules + needs_tree_build）
  2. 过滤 entries（应用 plan.ignore_rules）
  3. if intent=backup:
       if needs_tree_build:
           prep(backup_dir, plan.ignore_rules)
       backup(entries, tree, dry_run)        ← 不接触 Plan
  4. if intent=restore:
       restore(entries, tree, force)          ← 不接触 Plan
  5. if intent=apply:
       apply(entries, dry_run)                ← 不接触 Plan
```

ignore_rules 作为 Plan 的资产，存储在 `FileOpsPlan.ignore_rules` 字段中。Planner 持有整个 Plan 对象，在 Plan 生命周期内随时可取。

隔离由函数签名强制：`_execute_backup_plan` / `_execute_apply_plan` / `_execute_restore_plan` 不接收 `FileOpsPlan` 对象，只接收各自需要的具体字段（`entries` / `tree` / `flags`）。`ignore_rules` 不在参数列表中，primitive 无法访问。

## 文件清单

| 操作 | 文件 |
|------|------|
| 新建 | `src/modmanager/prep.py` |
| 修改 | `orchestrator/planner_fileops.py` — 加 `needs_tree_build` 字段，建树判断逻辑 |
| 修改 | `orchestrator/__init__.py` — 重构 `_dispatch_fileops`，prep 调度，primitive 签名改为具体字段 |
| 修改 | `src/modmanager/backup_ops.py` — 删建树函数，修改 `run_differential_backup` 接受预建 tree |
| 修改 | `src/modmanager/restore_ops.py` — 加 `.kmmignore` 复制回源目录 |
| 不修改 | `src/modmanager/apply_ops.py` |
| 文档 | `DESIGN_BACKUP_OPS.md`, `DESIGN_RESTORE_OPS.md`, `DESIGN_BACKUP_DIR.md` |

## 隐患检查

| 隐患 | 分析 |
|------|------|
| prep 成功后 backup 失败→部分备份 | tree 中 isbackuped 全为 false，下次 backup 只处理未备份条目。状态机正确处理 |
| Planner 需要读 backupinfo 判断 tree 完整性 | Planner 新职责。读取 `backup_dir/backupinfo.json` 检查 tree 字段非空且非 `{}`。已有 `load_backup_info` 函数 |
| ignore_rules 隔离 | 存储在 `FileOpsPlan`，primitive 通过签名隔离无法访问。prep 由 dispatch 传入 |
| backup 复制 `.kmmignore` 需要知道源目录结构 | 遍历 entries 中每个文件的祖先目录，收集 `.kmmignore`。此逻辑与 ignore 语义无关——只是文件复制 |

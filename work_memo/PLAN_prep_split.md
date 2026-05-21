# PLAN — prep 原语拆分 + ignore 下传阻断

> 创建：2026-05-21 by arch
> 状态：confirmed — 待施工

## 目标

1. 从 `backup_ops.py` 中拆分出 `prep.py`（创建 backup_dir 目录结构 + 建初始 tree + 写 `backupinfo.json`）
2. backup / restore / apply 彻底失去「知道 ignore」的必要性
3. `FileOpsPlan` 不再携带 `ignore_rules` 字段
4. backup 失去建树能力，只保留「更新树结点状态」的方法
5. restore 只读树，不写树

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
- 不含 `ignore_rules` 字段（由 `_dispatch_fileops` 局部变量持有）
- 新增 `needs_tree_build: bool` 字段——Planner 通过检查 backup_dir 是否存在、tree 是否完整来判定

**plan_fileops** 变化：
- 不再收集 ignore_rules（移到别处存储以便传给 prep）
- 调用 `build_backup_dirs` 后，对每个 backup_dir 检查是否需要建树
- 建树判断逻辑：`backup_dir` 目录不存在 **或** `backupinfo.json` 中的 tree 为空/不完整 → `needs_tree_build=True`

### `orchestrator/__init__.py` — `_dispatch_fileops`

新调度逻辑（intent=BACKUP）：

```python
if plan.needs_tree_build:
    # 收集 ignore_rules（Planner 在 dispatch 层收集，不在 plan_fileops 内）
    prep_backup_dir(backup_dir, ignore_rules)
# 然后执行 backup
_execute_backup_plan(plan, context, on_progress)
```

ignore_rules 的收集从 `plan_fileops` 移到 `_dispatch_fileops`——因为 prep 和 backup 的调度都在 dispatch 层完成，ignore 只传给 prep，不进入 Plan。

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

```
_dispatch_fileops:
  1. 收集 ignore_rules（调用 ignore_rules.collect_rules）
  2. plan_fileops（不再收集 ignore，不再过滤——过滤移到 dispatch 层）
  3. apply ignore 过滤到 entries + backup_dirs
  4. if intent=backup:
       if needs_tree_build:
           prep(backup_dir, ignore_rules)  ← ignore 在此消费
       backup(entries, tree)               ← 不接触 ignore
  5. if intent=restore:
       restore(entries, tree)              ← 不接触 ignore
  6. if intent=apply:
       apply(entries)                      ← 不接触 ignore
```

ignore_rules 在 `_dispatch_fileops` 中收集，作为该函数的局部变量持有。传给 prep 消费，不进入 `FileOpsPlan`。`_dispatch_fileops` 返回时自然释放。backup/restore/apply 在任何路径下都无法访问此变量——python 作用域强制隔离。

## 文件清单

| 操作 | 文件 |
|------|------|
| 新建 | `src/modmanager/prep.py` |
| 修改 | `orchestrator/planner_fileops.py` — 删 `ignore_rules` 字段，加 `needs_tree_build` |
| 修改 | `orchestrator/__init__.py` — dispatch 层收集 ignore，调度 prep+backup |
| 修改 | `src/modmanager/backup_ops.py` — 删建树函数，修改 `run_differential_backup` 接受预建 tree |
| 修改 | `src/modmanager/restore_ops.py` — 加 `.kmmignore` 复制回源目录 |
| 不修改 | `src/modmanager/apply_ops.py` |
| 文档 | `DESIGN_BACKUP_OPS.md`, `DESIGN_RESTORE_OPS.md`, `DESIGN_BACKUP_DIR.md` |

## 隐患检查

| 隐患 | 分析 |
|------|------|
| prep 成功后 backup 失败→部分备份 | tree 中 isbackuped 全为 false，下次 backup 只处理未备份条目。状态机正确处理 |
| Planner 需要读 backupinfo 判断 tree 完整性 | Planner 新职责。读取 `backup_dir/backupinfo.json` 检查 tree 字段非空且非 `{}`。已有 `load_backup_info` 函数 |
| ignore_rules 在 dispatch 层收集→与 plan_fileops 解耦 | 收集逻辑从 planner 移到 dispatch。过滤逻辑也移到 dispatch 层（entries 被 ignore 过滤发生在 dispatch，非 plan_fileops） |
| backup 复制 `.kmmignore` 需要知道源目录结构 | 遍历 entries 中每个文件的祖先目录，收集 `.kmmignore`。此逻辑与 ignore 语义无关——只是文件复制 |

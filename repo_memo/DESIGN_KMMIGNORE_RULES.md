# DESIGN_KMMIGNORE_RULES — kmmignore 规则规范

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 `.kmmignore` 文件规则——来源、收集、匹配。归属 Orchestrator Planner 层。
>
> Last update: 2026-05-25 — 移除硬编码 `.kmmbackup` 层（归属 bakignore/备份专属），kmmignore 仅含 `.kmmignore` 文件规则

---

## 一、定位

kmmignore 决定**哪些文件不参与 mod 管理**。规则由 `.kmmignore` 文件（gitignore 语法）定义，在 Planner 层统一收集，对所有操作（backup / apply / restore）生效。

> `.kmmbackup` 目录的备份专属排除行为见 `DESIGN_BACKUP_DIR.md`，与 kmmignore 无关。

实现模块：`src/modmanager/orchestrator/ignore_rules.py`。

---

## 二、规则来源

kmmignore 规则**仅来源于 `.kmmignore` 文件**（gitignore 语法），存放在源目录的各级子目录中。

> `.kmmbackup` 后缀目录的排除是**备份操作专属**行为，见 `DESIGN_BACKUP_DIR.md`。不属于 kmmignore 体系。

---

## 三、优先级语义

- Layer 1（硬编码）始终生效，不可覆盖
- Layer 2（`.kmmignore` 文件）遵循 gitignore 语义：子目录规则覆盖父目录规则

---

## 四、`.kmmignore` 文件规范

- 文件名：`.kmmignore`
- 语法：gitignore（兼容 `gitignore-parser` pip 包）
- 位置：源目录树中任意层级；规则仅对该目录及子目录生效
- 继承：子目录的 `.kmmignore` 与父目录规则合并，子目录规则优先级更高

---

## 五、Planner 调用接口

```python
from orchestrator.ignore_rules import collect_rules, should_ignore, IgnoreRuleSet

# 收集
rules: IgnoreRuleSet = collect_rules(source_roots)

# 匹配
if should_ignore(path, rules):
    # 排除
```

`plan_fileops()` 在推导 `backup_dirs` 后立即收集规则并过滤：
1. 过滤 `backup_dirs` 中的文件路径
2. 过滤 `entries_by_backup_dir` 中的条目
3. 过滤数记录在 `warnings` 中（`W_IGNORE_FILTERED`）

---

## 六、与 backupinfo tree 的关系

`backup_ops.build_dir_tree_with_hashes` 扫描源目录生成 tree 时，同样应用 `IgnoreRuleSet`：
- 被忽略的文件不进入 tree 的递归
- 这保证了 `isbackuped` 标记只对「应被管理的文件」生效

---

## 七、从 `.kmmbakignore` 迁移

文件名迁移（`.kmmbakignore` → `.kmmignore`）：

| 旧 | 新 |
|----|----|
| `.kmmbakignore` 文件名 | `.kmmignore` |
| 仅 backup 生效 | backup / apply / restore 全部生效（gitignore-parser 统一处理） |
| 归属 backup 原语 | 归属 Planner 层 |

> `user_config.bakignore` 字段**未**参与此次迁移——`bakignore` 与 `kmmignore` 语义不同：`bakignore` 系统自动维护、仅 backup 时生效（屏蔽旧备份目录），`kmmignore` 仅来自 `.kmmignore` 文件、全操作生效（gitignore 语法）。两者并存，各司其职。

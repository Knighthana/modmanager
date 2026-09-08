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

实现模块：`src/modmgr/orchestrator/fileops/planner/ignore_rules.py`。

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
- 跨文件语义（2026-09-08 明确）：匹配按「最深规则文件优先、命中即决」；不定义跨文件的 negation（`!`）回溯语义——需要否定规则时，请在**同一份** `.kmmignore` 文件内书写（文件内语义由 gitignore-parser 保证）

---

## 五、Planner 调用接口

```python
from orchestrator.fileops.planner.ignore_rules import collect_rules, should_ignore, IgnoreRuleSet

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

## 七、`bakignore`（user_config，仅 backup 生效）

> Last update: 2026-09-08 — 依据 2026-09-08 文件操作审计裁决，改写为可执行语义。

`user_config.bakignore` 是字符串后缀列表，**仅在 BACKUP intent 下作用于源内容侧**：

1. **prep 树扫描排除**：`prep_backup_dir()` 接收 `bakignore`，扫描源目录时跳过名字以任一后缀结尾的目录（`endswith` 匹配，无需点号约定——`270150.<hex>.kmmbackup`.endswith("kmmbackup") 恒真）。这同时覆盖历史备份目录与本次的（空）目标目录。
2. **planner 条目过滤**：`plan_fileops()` 过滤路径任一组件以 bakignore 后缀结尾的 mapping 条目（同时从 `backup_dirs` 文件列表与 `entries_by_backup_dir` 中剔除），并记录 `W_BAKIGNORE_FILTERED`（计数）。

**边界（负测试固化于 `tests/test_planner_fileops.py`）**：

- 本次派生的目标 backup_dir 是**输出容器**，永不作为 bakignore 匹配对象——即使其后缀在列表中（自动联动机制保证当前 baksuffix 恒在列表内，见 `DESIGN_USERCONFIG_OPS.md`）；
- 硬编码 `.kmmbackup` 层（`KMMBACKUP_SUFFIX`）始终生效，不可被 bakignore 配置覆盖；
- bakignore 不作用于 APPLY / RESTORE intent。

**列表维护**：初始值与 `baksuffix` 默认值一致；`baksuffix` 变更时自动追加新值（`userconfig_save`）。列表内容归自动联动机制与用户（SettingsPage 可增删）所有，代码层不做任何豁免或改写。

### 7.1 从 `.kmmbakignore` 迁移（历史）

文件名迁移（`.kmmbakignore` → `.kmmignore`）：

| 旧 | 新 |
|----|----|
| `.kmmbakignore` 文件名 | `.kmmignore` |
| 仅 backup 生效 | backup / apply / restore 全部生效（gitignore-parser 统一处理） |
| 归属 backup 原语 | 归属 Planner 层 |

> `bakignore` 与 `kmmignore` 语义不同：`bakignore` 系统自动维护、仅 backup 时生效（屏蔽备份容器目录的源内容），`kmmignore` 仅来自 `.kmmignore` 文件、全操作生效（gitignore 语法）。两者并存，各司其职。

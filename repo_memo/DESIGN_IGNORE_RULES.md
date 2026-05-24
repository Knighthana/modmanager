# DESIGN_IGNORE_RULES — 忽略规则规范

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义三层忽略规则体系——来源、收集、匹配。归属 Orchestrator Planner 层。
>
> Last update: 2026-05-21 — 新建；`.kmmbakignore` → `.kmmignore` 语义升级

---

## 一、定位

忽略规则决定**哪些文件不参与 mod 管理**。规则在 Planner 层统一收集，对所有操作（backup / apply / restore）生效。

实现模块：`src/modmanager/orchestrator/ignore_rules.py`。

---

## 二、三层规则

| 层 | 来源 | 格式 | 优先级 |
|:---:|------|------|:---:|
| 1 | 硬编码 | `.kmmbackup` 后缀目录始终排除 | 最高 |
| 2 | 用户配置 | `user_config.ignore` 数组（后缀/模式） | 中 |
| 3 | 文件规则 | 源目录各级 `.kmmignore` 文件（gitignore 语法） | 标准 |

规则收集后合并为一个 `IgnoreRuleSet`，匹配时按优先级判断。

---

## 三、优先级语义

- Layer 1（硬编码）始终生效，不可覆盖
- Layer 2（用户配置）对 Layer 3 有覆盖权——`user_config.ignore` 中的模式可额外排除文件
- Layer 3（`.kmmignore` 文件）遵循 gitignore 语义：子目录规则覆盖父目录规则

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
rules: IgnoreRuleSet = collect_rules(user_config, source_roots)

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

> `user_config.bakignore` 字段**未**参与此次迁移——`bakignore` 与 `ignore` 语义不同：`bakignore` 系统自动维护、仅 backup 时生效（屏蔽旧备份目录），`ignore` 用户手写、全操作生效（gitignore 语法）。两者并存，各司其职。

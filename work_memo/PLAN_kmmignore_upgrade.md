# 施工计划：`.kmmbakignore` → `.kmmignore` 语义升级

> 创建：2026-05-21 by arch
> 状态：confirmed — D22/D23 已裁决，待执行

## 目标

将 `.kmmbakignore`（"不备份"）升级为 `.kmmignore`（"不参与 mod 管理"）。
忽略逻辑从 backup 原语内部移动到 Planner 层，apply / restore 也受其约束。

## 影响范围

### A. 新模块

| 文件 | 内容 |
|------|------|
| `orchestrator/ignore_rules.py` | 独立忽略模块。封装 `gitignore-parser`。三层规则收集（硬编码 `.kmmbackup` + `user_config.ignore` + `.kmmignore` 文件）。对外暴露 `collect_rules()` + `should_ignore()`。 |

### B. 设计文档

| 文件 | 改动 |
|------|------|
| **新建** `DESIGN_IGNORE_RULES.md` | 忽略规则的权威定义——三层来源、gitignore 语法、Planner 调用接口 |
| `DESIGN_BACKUP_DIR.md` §5.4 | 排除规则更新：文件名 `.kmmignore`；来源引用 `DESIGN_IGNORE_RULES.md` |
| `DESIGN_BACKUP_OPS.md` §七 | 三层忽略规则 → 精简为引用 `DESIGN_IGNORE_RULES.md` |
| `DESIGN_MIGRATION_LAYERS.md` | Layer 1 增加 `orchestrator/ignore_rules.py` |

### C. 代码

| 文件 | 改动 |
|------|------|
| `orchestrator/ignore_rules.py` | 新建。`collect_rules(user_config, source_root) → IgnoreRuleSet`；`should_ignore(path, rules) → bool` |
| `orchestrator/planner_fileops.py` | `_collect_bakignore` → `_collect_ignore_rules`，调用 `ignore_rules.collect_rules`；三层规则对所有 intent 生效 |
| `orchestrator/__init__.py` | 清理残留 bakignore 引用 |
| `backup_ops.py` | `build_dir_tree_with_hashes` 接收 ignore 规则参数 |

### D. Schema

| 文件 | 改动 |
|------|------|
| `repo_spec/user_config.schema.json` | `bakignore` → `ignore`；description 更新 |

### E. 文件系统

| 操作 | 说明 |
|------|------|
| 存量 `.kmmbakignore` 文件 | 用户自行重命名为 `.kmmignore` |
| 新文件 | 一律创建为 `.kmmignore` |

## 实现顺序

1. 新建 `orchestrator/ignore_rules.py`
2. 新建 `DESIGN_IGNORE_RULES.md`
3. 修改 `planner_fileops.py`：收集 + 过滤
4. 修改 `user_config.schema.json`：字段改名
5. 修改 `DESIGN_BACKUP_DIR.md` §5.4 + `DESIGN_BACKUP_OPS.md` §七
6. 修改 `DESIGN_MIGRATION_LAYERS.md`
7. 更新 `work_memo/decisions.md`：D22/D23 标记为完成

## 已裁决
- [x] 文件名 `.kmmignore`
- [x] `user_config.bakignore` → `user_config.ignore`
- [x] 独立模块 `orchestrator/ignore_rules.py`

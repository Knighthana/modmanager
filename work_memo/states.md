# 工作状态

> arch 维护。smith 可向其中添加条目。

## 悬空待办（按优先级）

### P0 — 阻塞性缺陷
- [ ] **backupinfo tree 扫描源目录**：`backup_ops.py:258,263` — `build_dir_tree_with_hashes` 当前扫描 `backup_dir`，需改为扫描源目录并做 `isbackuped` 对照
- [ ] **backup `run_differential_backup` 目录处理**：`backup_ops.py:472` — `if src.is_dir(): shutil.copytree(...)` 违反 D15 file-to-file 约束，需删除
- [ ] **CLI restore 绕过 orchestrator**：`cli.py:338` — 调 `backup_ops.restore_from_backup` 直接，应为 `dispatch(Intent.RESTORE)`

### P1 — `.kmmignore` 升级
- [ ] 新建 `orchestrator/ignore_rules.py`（gitignore-parser 封装 + 三层规则收集）
- [ ] 文件名 `.kmmbakignore` → `.kmmignore`（存量文件用户自行重命名）
- [ ] `user_config.bakignore` → `user_config.ignore`（schema + 文档 + 代码）
- [ ] Planner `_collect_bakignore` → `_collect_ignore_rules`，backup/apply/restore 全量过滤
- [ ] 新建 `DESIGN_IGNORE_RULES.md`
- [ ] 更新 `DESIGN_BACKUP_DIR.md` §5.4、`DESIGN_BACKUP_OPS.md` §七
- [ ] 更新 `user_config.schema.json`

### P2 — 文档残修
- [ ] `DESIGN_BACKUP_OPS.md` §八：字段列表是否有重复定义需精简为引用

### P3 — 测试补全
- [ ] `apply_ops`：file-to-file 正例 + 目录拒绝 + dry_run + 返回契约
- [ ] `restore_ops`：hash 比对 / force 跳过 / 路径映射
- [ ] `planner_fileops`：preflight 决策分支 / 忽略收集 / backup_dir 分组
- [ ] `preflight`：apply gate / restore existence
- [ ] `ignore_rules`：三层收集 + gitignore 解析
- [ ] 恢复被 skip 的 24 个测试（改为测试 `dispatch()` 通路）
- [ ] restore 缺少的 warning：找不到备份实体 → warning 非 skipped；孤儿文件检测

## 已确认决策（本轮新增）

- **D22**: `.kmmbakignore` → `.kmmignore`；语义从「不备份」→「不参与 mod 管理」；归属 Planner 层；独立模块 `orchestrator/ignore_rules.py`
- **D23**: `user_config.bakignore` → `user_config.ignore`
- **D24**: backupinfo `tree` 扫描源目录（非 backup_dir），`isbackuped` 标记对照 backup_dir 副本

## FINISHED（本轮）

- [x] D1-D21 全部落地
- [x] `preflight.py` `check_backup_gate` 返回值修复
- [x] `resolver.py` `workspace_dir` None 回退修复
- [x] `_execute_backup_plan` `run_differential_backup` 签名修复
- [x] `restore_ops` 路径映射修复（content_root 逻辑）
- [x] 文档：7 个设计文档过期引用清理
- [x] 文档：backupinfo tree 来源修正（3 个文档）
- [x] 测试：import / schema_version 修复（380 passed, 0 failed）

# 2026-05-31 Decision/Plan 临时文档退场记录

## 目标
将 `work_memo` 中的临时决策文档迁移/对齐到 active 权威文档后，删除临时副本，避免与权威文档并存导致语义漂移。

## 本次完成项
1. 修订临时决策冲突（完成后删除源文件）
- P13：`source_path` 语义迁移为 `config_index`（必填入参兼出参，不持久化）。
- P22：`required` 改为 6 键；`bakignore` 非必填，允许缺省，存在时可为空数组。

2. 清理 active 文档残留
- 清理 `first_use` 文案残留。
- 清理 `source_path` / `user_config_path` 作为配置索引语义的残留。
- `DESIGN_STORAGE.md` 中 `bakignore` 必填标记改为可选，和 `repo_spec/user_config.schema.json` 对齐。

3. 收敛文档冗余
- 细化三份 backup 相关文档的 Supersedes 归属范围。
- 去重 backup/restore 中的重复 ignore 与流程断言描述。

4. 退场删除
- 已删除 `work_memo/decisions.md`。
- 已删除 `work_memo/PLAN_prep_split.md`。

## 迁移去向（权威承载）
- bootstrap/config 索引语义：`repo_memo/DESIGN_BOOTSTRAP.md`、`repo_memo/DESIGN_CONFIG_INDEX_PROTOCOL.md`
- user_config 字段与 required 约束：`repo_spec/user_config.schema.json`
- backup/restore 执行与结构：`repo_memo/DESIGN_BACKUP_OPS.md`、`repo_memo/DESIGN_RESTORE_OPS.md`、`repo_memo/DESIGN_BACKUP_DIR.md`

## 验收快照
- active 文档 `first_use` 命中：0
- active 文档 `source_path`/`user_config_path`（配置索引语义）命中：0
- active 文档中 `bakignore` 被描述为必填：0

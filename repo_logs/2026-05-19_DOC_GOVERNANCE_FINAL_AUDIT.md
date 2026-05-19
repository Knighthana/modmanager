# 2026-05-19 文档治理收敛审计快照

- 日期: 2026-05-19
- 范围: repo_memo, repo_logs, repo_spec, repo_test
- 结论: 本轮治理收敛已完成；主目录口径与历史归档分层符合当前规则。

## 一、审计目标

1. 验证 repo_memo 扁平化后不再依赖 archive/direct 子目录。
2. 验证 superseded 历史文档已迁入 repo_logs，并带日期前缀。
3. 验证主文档引用已切换为 repo_logs 历史文档命名。
4. 验证 repo_spec/repo_test 未引入过时目录引用。

## 二、检查结果

### 2.1 目录结构

- repo_memo 当前为扁平结构（无 archive/direct 子目录）。
- 历史文档已集中到 repo_logs，采用 DOC_ARCHIVE_2026-05-19_* 与 DOC_DIRECT_2026-05-19_* 命名。

### 2.2 过时路径残留

- 在 repo_memo/*.md 中检索:
  - repo_memo/archive
  - repo_memo/direct
  - /archive/
  - /direct/
- 结果: 未发现残留引用。

### 2.3 历史文档引用完整性

- 在 repo_memo/*.md 中检索历史文档名，命中为:
  - repo_logs/DOC_ARCHIVE_2026-05-19_DESIGN_GUI_WORKSPACE.md
  - repo_logs/DOC_ARCHIVE_2026-05-19_DESIGN_DATA_CLEANUP.md
- 结果: 主文档引用已切换到日期化归档命名。

### 2.4 规范与测试文档侧检查

- 在 repo_spec/**/*.md 检索过时目录与日期化归档名: 未发现冲突引用。
- 在 repo_test/**/*.md 检索过时目录与日期化归档名: 未发现冲突引用。

## 三、迁移映射（已完成）

- repo_memo/archive/DESIGN_GUI_WORKSPACE.md -> repo_logs/DOC_ARCHIVE_2026-05-19_DESIGN_GUI_WORKSPACE.md
- repo_memo/archive/DESIGN_DATA_CLEANUP.md -> repo_logs/DOC_ARCHIVE_2026-05-19_DESIGN_DATA_CLEANUP.md
- repo_memo/archive/DESIGN_SVG_CACHE_AND_FOREST_LIST.md -> repo_logs/DOC_ARCHIVE_2026-05-19_DESIGN_SVG_CACHE_AND_FOREST_LIST.md
- repo_memo/direct/AUDIT-ALIGN.md -> repo_logs/DOC_DIRECT_2026-05-19_AUDIT-ALIGN.md
- repo_memo/direct/TODO-uiState-workspace.md -> repo_logs/DOC_DIRECT_2026-05-19_TODO-uiState-workspace.md

## 四、风险与建议

- 当前未发现阻断性风险。
- 建议后续在新增 superseded 文档时继续采用 repo_logs 日期前缀命名，避免主目录语义回流。
- 建议在文档审计任务模板中固定两条检索:
  - 过时目录残留检索（archive/direct）
  - 主文档对历史文档的日期化命名检索

## 五、关联提交

- 17c40bc docs(governance): align workspace authority and remove stale references
- dc46e8d docs(repo_memo): archive superseded workspace migration docs
- a0eba73 docs(repo_memo): move superseded svg design to archive
- 28dd7ba docs(frontend): remove deprecated workspace key from anti-pattern example
- e257d5d docs(governance): flatten repo_memo and relocate stale docs to repo_logs

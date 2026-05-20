# 当前决策记录

> 本文件由 arch 维护，smith 在每次任务前检查 L1 约束是否与既有决策冲突。
> 本文件不是契约权威来源；若与 `repo_memo/` 冲突，以 `repo_memo/` 为准。

## 2026-05-20 术语与接口清退

### 已确认决策

- **D1**: 删除整个 `cli-hmi/` 目录，同时清理所有外部文档中的 `cli-hmi` 路径引用
- **D2**: `engine.py` 中 `_check_dir_tree_transition()` 移除 `"directory"` → `"dir"` 向后兼容代码，强制仅接受 `"dir"`
- **D3**: `tests/test_orchestrator.py:352` `"kmmbackup_"` → `"kmmbackup"`（非违例测试，属旧值残留）
- **D4**: 前端 `RulesOverviewPage.vue`：`rulenamespace` 空时回退 `"anonymousnamespace"`，`rulename` 空时回退 `"unknownrulename"`（不再回退到 `file.name`）
- **D5**: 全仓库文档中清除 `appitemid`、`dommod`、`islbfdvdflocate` 三个历史别名的所有出现
- **D6**: `engine.py` 私有 dataclass `ForestTree` 不重命名
- **D7**: 警告码 `W_FOREST_BRANCHING` 不重命名（报错是给人看的）
- **D8**: `description/` 目录下的示例文件由用户自行修改，仅提供修改建议；与 D5 冲突时 D8 优先（即 `description/database.json.example` 由 arch 输出建议，smith 不直接编辑）

- **D9**: `repo_spec/` schema 补全与字段统一施工——新增 9 个 schema + 修改 10 个既有 schema（原禁区"不修改 schema 文件 / repo_spec JSON"已由 user 直接指令覆盖，开发阶段无生产数据）

### 禁区

- 不跑测试

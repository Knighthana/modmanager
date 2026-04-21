# Tasklist

## Future M1 Patch（暂缓，非今日执行）

### P1: meta_tag 传导并入 M1
1. 在 changerequest 中传导 `action_meta_tag`。
2. 让 forest/final_mapping 保留可回溯标签。
3. 更新 `output_schema` 以反映新字段。
4. 补齐 schema/engine/contract 测试。

### P2: actionorder 辅助决议并入 M1
1. 仅在树生成后用于分支辅助决策。
2. `actionorder` 为空、相等、不可判定时回退人工拍板。
3. 保留用户强制手动选择开关。

### P3: replace 历史映射补丁并入 M1
1. 把 M1 外的历史映射解析层并入引擎主链。
2. 解决“应使用 A 却误用 E”的历史覆盖风险。
3. 保持与备份语义兼容，不引入“强制备份源文件”语义。

## Today Scope
- 文档持久化与边界冻结。
- 不修改 M1 执行逻辑。

## Closeout Follow-up
1. 统一 `description/workflow_restrict.md` 与 `repo_memory/README.md` 的口径：保持“默认忽略 + Plan 可授权例外”。
2. 追加收工 checkpoint 到 `MEMORY_SYNC_INDEX.md`，标记本轮实现交接已完成。
3. 复核本轮变更仅包含文档与索引收尾项。
4. 若复核通过，执行一次 git 提交。
5. 建议提交标题：`docs: finalize implement handoff for deferred M1 work`
6. 建议提交说明：`align description wording with repo_memory authority`; `persist handoff checkpoint and deferred M1 boundaries`

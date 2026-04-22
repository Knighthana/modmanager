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

## Current Doc Freeze: aggregated_rule_set DSL
1. 冻结 `from` / `into` 为 `list[string]`，补 `from_type` / `into_type` 显式类型契约。
2. 冻结 action 分流：`replace`/`create` 共享写入校验，`delete` 单独校验，`hold` 直接忽略。
3. 冻结 `path -> path` 语义为复制目录本身，不接受“复制内容”式兜底解释。
4. 冻结 `delete` 语义：只读 `into` 与 `into_type`；`from` / `from_type` 完全忽略。
5. 冻结冲突规则：同 action 多源同目标报 `E_ACTION_INTERNAL_COLLISION`；`delete` 与非 `delete` 同目标同批报错。
6. 冻结兼容期策略：保留 `rename_then_replace`，但视为兼容 action，不再作为主路径能力扩展中心。

## Implement Handoff Notes
1. `def_action=hold` 只影响未显式声明 `action` 的子条目；显式非 `hold` 子条目仍正常处理。
2. `hold` 条目不进入解析链，因此不应要求其提供 `from`、`into`、`from_type`、`into_type`。
3. 两份 `aggregated_rule_set.json.example` 必须保持 repo_memory -> description 的单向镜像同步。

## Closeout Follow-up
1. 统一 `description/workflow_restrict.md` 与 `repo_memory/README.md` 的口径：保持“默认忽略 + Plan 可授权例外”。
2. 追加收工 checkpoint 到 `MEMORY_SYNC_INDEX.md`，标记本轮实现交接已完成。
3. 复核本轮变更仅包含文档与索引收尾项。
4. 若复核通过，执行一次 git 提交。
5. 建议提交标题：`docs: finalize implement handoff for deferred M1 work`
6. 建议提交说明：`align description wording with repo_memory authority`; `persist handoff checkpoint and deferred M1 boundaries`

## Near-term Forest Visualization
1. `forest_visual` 核心模块。
2. ASCII renderer。
3. DOT renderer。
4. DOT -> SVG renderer。
5. 目标：先让人能稳定看到 forest 的形状。

## M3 Backlog: Forest Visualization Expansion
1. HTML fragment。
2. HTML standalone。
3. Plot renderer。
4. trace/meta 扩展字段的可视化兼容验证。

## M4 Backlog: GUI Visualization And Interaction
1. hover 整链高亮。
2. 分叉节点超链接与详情展示。
3. 用户选枝 UI。
4. 外部 annotator / transformer / custom visualizer 插件运行链。
5. 老浏览器 fallback 与 GUI 集成策略。

## Visualization Compatibility Rule
1. 可视化模块只依赖当前最小必需字段建图。
2. 未来 M1 patch 若在 `forest` / `changerequest` 中增加 trace/meta 标签，可视化模块必须容忍未知扩展字段并可透传到中间模型。

## Document Persistence Checklist (Before Coding)
1. 在 `FOREST_VISUALIZATION_DESIGN.md` 固化数据流、坑位清单、Go/No-Go、最小验收用例。
2. 在 `IMPLEMENTATION_BRIEF.md` 记录“文档先行”开工门槛。
3. 在 `MEMORY_SYNC_INDEX.md` 追加本轮开发指导文档同步记录。

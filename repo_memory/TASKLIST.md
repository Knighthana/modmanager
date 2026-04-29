# Tasklist

## Future M1 Patch（暂缓，非今日执行）

### P1: _ref 传导并入 M1
1. 在 changerequest 中传导 `provenance_ref`、`action_order`、`sidecar_ref`。
2. `_ref` 缺失或空值时回退为 `404` 并记录 warning，不得直接崩溃。
3. 让 forest/final_mapping 保留可回溯字段。
4. 更新 `output_schema` 以反映新字段。
5. 补齐 schema/engine/contract 测试。

### P2: action_order 冲突决议并入 M1
1. `action_order` 仅接受 int，默认值为 `0`。
2. 仅在树生成后用于分支辅助决策，不得作为规则正确性的兜底来源。
3. 命中过程冲突且双方 `action_order` 相等，或任一方为 `0` 时，直接抛错。
4. 保留用户强制手动选择开关，但不做隐式自动仲裁。

### P3: delete 捋枝并入 M1
1. 命中 delete 结点时，按当前 forest 结构模型将其视为无 source-path 的叶请求，不参与后续父结点搜索。
2. 在树生成后的决议阶段，若有效叶为 delete，则将其折叠提升为对根 target 的删除请求。
3. 执行阶段删除 `final_mapping.path` 对应文件；不采用“提升子节点并重挂祖父”的树重写语义。

### P4: replace 历史映射补丁并入 M1
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
7. 冻结类型体系：不支持 `file_and_path`；`from_type` / `into_type` 仅允许 `file|path`。
8. 冻结等价表达：`cp -r src/* dest/` 必须拆成两条 action，一条目录型，一条文件型。
9. 冻结支持场景：`from_type=path` + 目录 glob（如 `shiplander v1.9/*/`）属于 DSL 内支持场景；当前缺口若存在，归因于执行层实现不完整，而非边界外需求。

## Implement Handoff Notes
> 2026-04-30 更新：`def_action` 继承和 hold 过滤已移交聚合器，M1 不再处理。
> 每条 action 在进入 M1 时 `action` 和 `destin` 均为显式值。

1. `def_action=hold` 只影响未显式声明 `action` 的子条目；显式非 `hold` 子条目仍正常处理。（聚合器职责）
2. `hold` 条目不进入解析链，因此不应要求其提供 `from`、`into`、`from_type`、`into_type`。（聚合器过滤阶段）
3. 两份 `aggregated_rule_set.json.example` 必须保持 repo_memory -> description 的单向镜像同步。
4. `description/` 只用于 user-plan 交流；implement 默认以 `repo_memory/` 为标准源。
5. `user_config.json.example` 的权威样例位于 `repo_memory/`，字段固定为 `path_alias`、`path_handle`、`path_target`。

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

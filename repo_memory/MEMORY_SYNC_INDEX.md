# Memory Sync Index

用于记录从 /memories 到 repo_memory 的摘要同步。

## 记录规则
- 仅同步长期有效结论，不复制临时对话过程
- 每条记录包含来源、目标、时间、责任人、状态
- 若发现冲突，以 repo_memory 契约为准，并在备注说明

## 迁移完成度看板

| 分类 | 总数 | 已迁移 | 未迁移 | 完成度 |
|---|---:|---:|---:|---:|
| 关键执行文档 | 5 | 5 | 0 | 100% |
| 会话摘要输入 | 3 | 3 | 0 | 100% |

说明：关键执行文档指 `TERMINOLOGY.md`、`STEAM_DISCOVERY.md`、`DATABASE_FIELDS.md`、`process_description.md`、`IMPLEMENTATION_BRIEF.md`。

## 未迁移项模板

当后续发现新来源时，按以下模板追加：

| 时间 | 来源 | 计划目标 | 原因 | 预计完成 | 责任人 | 状态 |
|---|---|---|---|---|---|---|
| YYYY-MM-DD | /memories/session/xxx.md | repo_memory/xxx.md | 待归档/待裁剪/冲突待解 | YYYY-MM-DD | implementation-agent | pending |

| 时间 | 来源 | 目标 | 责任人 | 状态 | 备注 |
|---|---|---|---|---|---|
| 2026-04-21 | /memories/patterns.md | ENGINEERING_PATTERNS.md | implementation-agent | synced | 工程模式已摘要化 |
| 2026-04-21 | /memories/session/m1_spec.md | M1_EXECUTION_CONTRACT.md | implementation-agent | synced | 仅保留 M1 执行约束 |
| 2026-04-21 | /memories/session/conflict_analysis.md | OPEN_CONFLICTS.md | implementation-agent | synced | 仅保留未解决冲突 |
| 2026-04-21 | TEMP_PROGRESS_TODO.md | IMPLEMENTATION_BRIEF.md / doc_contract_snapshot.md | implementation-agent | synced | 已同步 CLI 暴露、回归快照与下一轮收敛项 |
| 2026-04-21 | IMPLEMENTATION_AGENT_HANDOFF.md | IMPLEMENTATION_BRIEF.md / doc_contract_snapshot.md | implementation-agent | synced | 已同步交接范围与验证结论 |
| 2026-04-21 | /memories/session/plan.md (P0-P2) | IMPLEMENTATION_BRIEF.md / doc_contract_snapshot.md | implementation-agent | synced | 备份/替换/恢复模块实现（Phase 7-12），189/189 |
| 2026-04-21 | /memories/session/plan.md (Phase 13) | OPEN_CONFLICTS.md / IMPLEMENTATION_BRIEF.md / doc_contract_snapshot.md | implementation-agent | synced | Phase 13 落地（dirty-state/conflict/orphan），194/194 |
| 2026-04-21 | 用户决策（冲突 #2/#3 拍板） | OPEN_CONFLICTS.md / IMPLEMENTATION_BRIEF.md | implementation-agent | synced | 关闭 #2 两阶段 hash 校验、#3 结构冻结+单向演进措辞；实现无需改动 |
| 2026-04-22 | 用户决策（目录职责治理 + 示例同步） | README.md / description/workflow_restrict.md / json.example 布局 | implementation-agent | synced | 固化角色矩阵；description 默认非实现输入；示例单向同步 repo_memory -> description；新增 work_memo 临时区 |
| 2026-04-22 | 用户决策（replace/builder/meta_tag 文档持久化） | README.md / TERMINOLOGY.md / IMPLEMENTATION_BRIEF.md / RULE_AGGREGATION_DESIGN.md / REPLACE_SERVICE_DESIGN.md / BACKUP_DIR_BUILDER_DESIGN.md / TASKLIST.md | implementation-agent | synced | 固化“今天不改 M1、未来可并入 M1”阶段策略；新增 A/E 历史映射风险定义与 Future M1 Patch 清单 |
| 2026-04-22 | 用户决策（文档收工交接包） | description/workflow_restrict.md / TASKLIST.md / MEMORY_SYNC_INDEX.md | implementation-agent | synced | 统一“默认忽略 + Plan 可授权例外”口径；补收工 checkpoint 与建议提交信息 |
| 2026-04-22 | 用户决策（forest 可视化范围收缩与排期） | IMPLEMENTATION_BRIEF.md / FOREST_VISUALIZATION_DESIGN.md / TASKLIST.md / MEMORY_SYNC_INDEX.md | implementation-agent | synced | 近期仅 core + ASCII + DOT + DOT->SVG；HTML/Plot 入 M3；GUI 交互与插件运行链入 M4；保留未来 M1 trace/meta 扩展兼容 |
| 2026-04-22 | 用户决策（forest 最小绘图系统开发指导） | FOREST_VISUALIZATION_DESIGN.md / IMPLEMENTATION_BRIEF.md / TASKLIST.md / MEMORY_SYNC_INDEX.md | implementation-agent | synced | 固化数据流、预排坑位、Go/No-Go、最小验收用例；确认本轮仅文档持久化 |
| 2026-04-22 | 用户决策（aggregated_rule_set DSL 冻结） | IMPLEMENTATION_BRIEF.md / TASKLIST.md / RULE_AGGREGATION_DESIGN.md / aggregated_rule_set.json.example / description/TODO.md | implementation-agent | synced | 冻结 list[string] + type 契约；hold 仅在最终解析为 hold 时跳过；delete 只读 into；path->path 复制目录本身；repo_memory 示例已同步到 description |
| 2026-04-23 | 用户决策（_ref 模型冻结与 repo_memory 权威化） | user_config.json.example / aggregated_rule_set.json.example / filemappingforest.json.example / TERMINOLOGY.md / TASKLIST.md / RULE_AGGREGATION_DESIGN.md / IMPLEMENTATION_BRIEF.md / MEMORY_SYNC_INDEX.md | implementation-agent | synced | 固化 `path_alias/path_handle/path_target`；动作级统一为 `provenance_ref/action_order/sidecar_ref`；`_ref` 缺失回退 `404` + warning；delete 叶折叠为根 target 删除；repo_memory 作为标准源 |
| 2026-04-30 | 用户决策（聚合器完整设计 v2） + 全量文档审计 | RULE_AGGREGATION_DESIGN.md / aggregated_rule_set.json.example / TERMINOLOGY.md / IMPLEMENTATION_BRIEF.md / TASKLIST.md / COMPLETION_SUMMARY.md / MEMORY_SYNC_INDEX.md | arch | synced | 全面重写聚合器设计；废弃 source_trace_map；provenance_ref 固定为绝对路径；聚合器接管全部鉴权和 def_destin/def_action 继承具体化；M1 移除 validate_forest_roots、sub 检查和继承逻辑；rule_set 顶层 key mod→operation；输出无 def_destin/def_action；sidecar_ref 外部注入接口保留；多规则合并策略完整决策（文件内具体化→跨文件合并→鉴权过滤）；审计并修复 5 个文件中的 7 处冲突（TERMINOLOGY/IMPLEMENTATION_BRIEF/TASKLIST 中的旧语义描述、示例中的 path_handle 格式 provenance_ref） |

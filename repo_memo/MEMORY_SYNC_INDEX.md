# Memory Sync Index

用于记录从 /memories 到 repo_memo 的摘要同步。

## 记录规则
- 仅同步长期有效结论，不复制临时对话过程
- 每条记录包含来源、目标、时间、责任人、状态
- 若发现冲突，以 repo_memo 契约为准，并在备注说明

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
| YYYY-MM-DD | /memories/session/xxx.md | repo_memo/xxx.md | 待归档/待裁剪/冲突待解 | YYYY-MM-DD | implementation-agent | pending |

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
| 2026-04-22 | 用户决策（目录职责治理 + 示例同步） | README.md / description/workflow_restrict.md / json.example 布局 | implementation-agent | synced | 固化角色矩阵；description 默认非实现输入；示例单向同步 repo_memo -> description；新增 work_memo 临时区 |
| 2026-04-22 | 用户决策（replace/builder/meta_tag 文档持久化） | README.md / TERMINOLOGY.md / IMPLEMENTATION_BRIEF.md / RULE_AGGREGATION_DESIGN.md / further/REPLACE_SERVICE_DESIGN.md / BACKUP_DIR_BUILDER_DESIGN.md / TASKLIST.md | implementation-agent | synced | 固化“今天不改 M1、未来可并入 M1”阶段策略；新增 A/E 历史映射风险定义与 Future M1 Patch 清单 |
| 2026-04-22 | 用户决策（文档收工交接包） | description/workflow_restrict.md / TASKLIST.md / MEMORY_SYNC_INDEX.md | implementation-agent | synced | 统一“默认忽略 + Plan 可授权例外”口径；补收工 checkpoint 与建议提交信息 |
| 2026-04-22 | 用户决策（forest 可视化范围收缩与排期） | IMPLEMENTATION_BRIEF.md / FOREST_VISUALIZATION_DESIGN.md / TASKLIST.md / MEMORY_SYNC_INDEX.md | implementation-agent | synced | 近期仅 core + ASCII + DOT + DOT->SVG；HTML/Plot 入 M3；GUI 交互与插件运行链入 M4；保留未来 M1 trace/meta 扩展兼容 |
| 2026-04-22 | 用户决策（forest 最小绘图系统开发指导） | FOREST_VISUALIZATION_DESIGN.md / IMPLEMENTATION_BRIEF.md / TASKLIST.md / MEMORY_SYNC_INDEX.md | implementation-agent | synced | 固化数据流、预排坑位、Go/No-Go、最小验收用例；确认本轮仅文档持久化 |
| 2026-04-22 | 用户决策（aggregated_rule_set DSL 冻结） | IMPLEMENTATION_BRIEF.md / TASKLIST.md / RULE_AGGREGATION_DESIGN.md / aggregated_rule_set.json.example / description/TODO.md | implementation-agent | synced | 冻结 list[string] + type 契约；hold 仅在最终解析为 hold 时跳过；delete 只读 into；path->path 复制目录本身；repo_memo 示例已同步到 description |
| 2026-04-23 | 用户决策（_ref 模型冻结与 repo_memo 权威化） | user_config.json.example / aggregated_rule_set.json.example / filemappingforest.json.example / TERMINOLOGY.md / TASKLIST.md / RULE_AGGREGATION_DESIGN.md / IMPLEMENTATION_BRIEF.md / MEMORY_SYNC_INDEX.md | implementation-agent | synced | 固化 `path_alias/path_handle/path_target`；动作级统一为 `provenance_ref/action_order/sidecar_ref`；`_ref` 缺失回退 `404` + warning；delete 叶折叠为根 target 删除；repo_memo 作为标准源 |
| 2026-04-30 | 用户决策（同 mod 冲突自动裁决） + Phase 1 提问 | engine.py / TASKLIST.md / IMPLEMENTATION_BRIEF.md / direct/QUESTIONS_BOOTSTRAP.md | arch | synced | 同 mod 内多条 action 命中同一目标时自动取最后一条（而非产生分支冲突），120→0；Bootstrap 模块设计启动，8 个待决策问题归档 |
| 2026-04-30 | Phase 1 实现完成 | bootstrap.py / orchestrator.py / cli.py / direct/TASKS_PHASE1_BOOTSTRAP_ORCHESTRATOR.md / IMPLEMENTATION_BRIEF.md / TASKLIST.md / MEMORY_SYNC_INDEX.md | arch | synced | bootstrap.py（discover_user_config + generate_database）+ orchestrator.py（compute/backup/apply/run）+ CLI 适配 + 18 new tests，全量 261 通过 |
| 2026-04-30 | Phase 2 设计 + 7 决策确认（含 Q7 方案 A） | direct/DESIGN_PHASE2_WEB_API.md / TASKLIST.md / IMPLEMENTATION_BRIEF.md / MEMORY_SYNC_INDEX.md | arch | synced | FastAPI / 全部 6 操作暴露 / localhost 无认证 / 全异步 SSE / 独立子包 / ApiResponse 适配层 / 方案 A 独立对等（共享内核，耦合度最低） |
| 2026-04-30 | Phase 3 实现完成 | frontend/** + forest_visual.py + app.py + TASKLIST.md + IMPLEMENTATION_BRIEF.md | arch | synced | Vue 3 SPA（Forest SVG 交互+冲突裁决+规则/备份页面）+ M3 SVG 升级（data-*/title/desc）+ FastAPI static mount + SPA fallback；前端 14 tests + Python 276 tests 全通过 |
| 2026-04-30 | Phase 3 13 决策确认 + 设计完成 | direct/QUESTIONS_PHASE3.md / direct/DESIGN_PHASE3_GUI.md / TASKLIST.md / IMPLEMENTATION_BRIEF.md / MEMORY_SYNC_INDEX.md | arch | synced | Vue 3 + Vite + TypeScript + Element Plus + Pinia；SPA + Vue Router；后端 SVG → v-html 交互；static mount + SPA fallback；M3 前置（SVG 节点属性升级）
| 2026-04-30 | Phase 2 实现完成 | `src/modmanager_web/**` / pyproject.toml / tests/test_web_api.py / TASKLIST.md / IMPLEMENTATION_BRIEF.md / MEMORY_SYNC_INDEX.md | arch | synced | `modmanager_web` 独立子包（schemas+adapters+sse+routes+app+entry），15 new tests，全量 276 通过，`modmanager/*` 零改动 |
| 2026-05-06 | P0 森林模型重构：独立根+引用 | `direct/DESIGN_P0_FOREST_RISK_ANALYSIS.md` / `direct/DESIGN_P0_FOREST_IMPLEMENTATION.md` / `engine.py` / `forest_visual.py` / `orchestrator.py` / `frontend/*` / `TASKLIST.md` | arch | synced | ForestTree dataclass + 5 个解析函数；输出 `forest`→`trees`；`W_DELETE_LEAF_PROMOTED`→`W_SOURCE_DELETED`；前端 TreeNode 类型；全栈同步切换，296 tests |
| 2026-05-06 | P1 Backup 实现：builder + 循环防护 | `direct/DESIGN_P1_BACKUP.md` / `backup_dir_builder.py` / `backup_ops.py` / `acf_parser.py` / `orchestrator.py` / CLI/Web/前端适配 | arch | synced | workshop/custom time 源；.kmmbakignore；backup_ops 硬编码 kmmbackup_ 过滤；CLI/Web backup_dir 可选化；319 tests |
| 2026-05-06 | P2 引擎细节修复 | `engine.py`（delete→create warning）+ 术语统一 | arch | synced | `deleted_targets` 集合追踪；1 处术语纠正；320 tests |
| 2026-05-06 | P3 GUI 增强：全部/仅分岔 + hover 高亮 + 点击选枝 | `direct/DESIGN_P3_GUI2.md` / `ForestPage.vue` / `ForestViewer.vue` / `forest_visual.py` | arch | synced | el-switch 切换；data-tree-refs/referenced-by 属性；整链高亮；选枝模式交互；322 Python + 18 前端 tests |
| 2026-05-07 | P4 GUI 缺口补齐：ConflictsPage 参数持久化 + RulesPage API + BackupPage API + pipeline restore 端点 | `direct/DESIGN_P4_GUI_GAP_CLOSURE.md` / `routes/rules.py` / `routes/backups.py` / `pipeline.py` / `BackupPage.vue` / `RulesPage.vue` / `ConflictsPage.vue` / `forest.ts` | arch | synced | 25 任务全部完成；新增 `/api/rules/scan+read`、`/api/backups/list+inspect`、`/api/pipeline/restore`（独立端点，不耦合 apply）；ForestStore discoverDatabase 副作用拆分；338 Python + 40 前端 tests |

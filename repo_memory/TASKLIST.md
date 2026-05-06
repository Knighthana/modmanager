# Tasklist

## ✅ Completed

### M1 Core + Patches
- 核心映射引擎（6 条规则 + 环检测 + 分枝）✅
- `def_destin`/`def_action` 继承移交聚合器 ✅
- sub 鉴权移交聚合器，移除 `validate_forest_roots` ✅
- 同 mod 内 actionlist 自动裁决（later wins）✅
- delete 叶折叠 ✅
- `provenance_ref` / `action_order` / `sidecar_ref` 在 changerequest 中传导 ✅

### 备份/替换/恢复（Phases 7–13）
- 差异备份、替换执行、从备份恢复 ✅
- 脏数据检测、冲突检查、orphan 治理 ✅

### 聚合器
- 完整聚合器实现（6 步流水线）✅
- 权限鉴权（game + sub）✅
- 多规则合并策略 ✅

### Forest 可视化
- ASCII / DOT / DOT→SVG / HTML standalone ✅

### Steam 发现与数据库
- 多库发现、CRUD、liveupdate/regen ✅

---

## Phase 1: Bootstrap & Orchestrator ✅

在 Web GUI 之前，需要初始化和调度层把现有模块串成端到端流水线。

### 已完成的模块

| 模块 | 文件 | 职责 |
|------|------|------|
| Bootstrap | `src/modmanager/bootstrap.py` ✅ | user_config 三级搜索+合并、Steam 数据库生成 |
| Orchestrator | `src/modmanager/orchestrator.py` ✅ | 流水线调度：接收初始状态，按序驱动聚合→映射→备份→应用；支持进度回调；预留多游戏并行调度扩展点 |
| CLI 适配 | `src/modmanager/cli.py` ✅ | `_handle_backup`/`_handle_apply` 改为调用 orchestrator |
| 测试 | `tests/test_bootstrap.py` ✅ (11 tests) | `tests/test_orchestrator.py` ✅ (7 tests) |

各子模块（engine、aggregator、backup_ops）独立存在、可单独测试，orchestrator 只做编排。

### 决策记录
全部 8 个问题已决策：见 `repo_memory/direct/QUESTIONS_BOOTSTRAP.md`

---

## Phase 2: Web API 层 ✅

将 bootstrap + engine + backup 暴露为 REST 接口。

设计文档：`repo_memory/direct/DESIGN_PHASE2_WEB_API.md`
决策记录：7 个问题全部已确认 ✅（含 Q7 方案 A 独立对等）

### 已完成的模块（`modmanager_web` 独立子包）

| 模块 | 文件 | 职责 |
|------|------|------|
| Schemas | `src/modmanager_web/schemas.py` ✅ | Pydantic 请求/响应模型 |
| Adapters | `src/modmanager_web/adapters.py` ✅ | PipelineResult → ApiResponse 转换 |
| SSE Bridge | `src/modmanager_web/sse.py` ✅ | 同步 ProgressCallback → 异步 SSE 流桥接 |
| Routes | `src/modmanager_web/routes/{config,database,pipeline}.py` ✅ | REST 端点 |
| App | `src/modmanager_web/app.py` ✅ | FastAPI 应用工厂 |
| Entry | `src/modmanager_web/__main__.py` ✅ | uvicorn 启动 |
| 测试 | `tests/test_web_api.py` ✅ (15 tests) | |

全量 276 tests 通过（261 existing + 15 new）。`modmanager/*` 零改动。

## Phase 3: 前端 GUI ✅

规则浏览器、Forest 可视化嵌入、冲突裁决 UI、备份/恢复控制台。

决策记录：`repo_memory/direct/QUESTIONS_PHASE3.md`（13 个问题全部已决策 ✅）
设计文档：`repo_memory/direct/DESIGN_PHASE3_GUI.md`

### 需要新增的模块

| 模块 | 位置 | 职责 |
|------|------|------|
| Vue SPA | `frontend/` | Vue 3 + Vite + TypeScript + Element Plus + Pinia |
| M3 前置 | `forest_visual.py`（修改） | SVG 节点嵌入交互属性 |
| 静态挂载 | `app.py`（修改） | FastAPI StaticFiles + SPA fallback |

### 四个页面

| 页面 | 路由 | 职责 |
|------|------|------|
| ForestPage | `/forest` | 参数表单 + Forest SVG 展示 + zoom/pan + SSE 进度 |
| ConflictsPage | `/conflicts` | 冲突列表 + 候选选择 + 重新计算 |
| RulesPage | `/rules` | kmm_rule 文件浏览 |
| BackupPage | `/backup` | 备份列表 + 恢复操作 |

### 术语规范
- 树/图上的元素统一用 **"结点"**（非"节点"）
- 见 `repo_memory/direct/DESIGN_PHASE3_GUI.md` §14

### 测试
- 前端 Vitest: 14 tests 全部通过
- Python: 276 tests 全部通过
- frontend/ 构建成功，产物嵌入 FastAPI 静态文件

---

## Phase P0: 森林模型重构 ✅

将现有"刨根移栽"式 delete 传播模型替换为"独立根 + 引用"模型。

**核心设计文档**：
- 风险分析：`repo_memory/direct/DESIGN_P0_FOREST_RISK_ANALYSIS.md`
- 实现方案：`repo_memory/direct/DESIGN_P0_FOREST_IMPLEMENTATION.md`

**决策**：
- 激进全栈切换，不接受技术债
- delete 源失效 → 跳过 + warning（不报错，不传播）
- 目录 delete 不裂变 → 改用祖先路径前缀检查
- `branch_decisions` 格式向后兼容扩展

| # | 任务 | 模块 | 状态 |
|---|------|------|------|
| P0-01 | ForestTree dataclass 定义 | `engine.py` | done |
| P0-02 | `_build_forest_trees()` 实现 | `engine.py` | done |
| P0-03 | `_topological_sort_by_refs()` 实现 | `engine.py` | done |
| P0-04 | `_ancestor_deleted()` 实现 | `engine.py` | done |
| P0-05 | `_resolve_trees_bottom_up()` 实现 | `engine.py` | done |
| P0-06 | `_build_output()` 实现 | `engine.py` | done |
| P0-07 | ForestTree 构建单元测试 | `test_engine.py` | done |
| P0-08 | 拓扑排序单元测试 | `test_engine.py` | done |
| P0-09 | 祖先检查单元测试 | `test_engine.py` | done |
| P0-10 | 自底向上解析单元测试 | `test_engine.py` | done |
| P0-11 | 重写 `compute_mapping()` 下半段 | `engine.py` | done |
| P0-12 | 移除 `_resolve_effective_leaf_request()` | `engine.py` | done |
| P0-13 | 移除 `W_DELETE_LEAF_PROMOTED` 逻辑 | `engine.py` | done |
| P0-14 | 更新 engine 集成测试 | `test_engine.py` | done |
| P0-15 | 更新契约测试 (forest→trees) | `test_contract.py` | done |
| P0-16 | 更新集成 fixtures 测试 | `test_integration_fixtures.py` | done |
| P0-17 | orchestrator PipelineResult 适配 | `orchestrator.py` | done |
| P0-18 | Web API schemas/adapters/routes 适配 | `modmanager_web/*` | done |
| P0-19 | 下游模块测试更新 | `tests/*` | done |
| P0-20 | 重写 `_build_tree_graph_model()` | `forest_visual.py` | done |
| P0-21 | 重写 `_render_ascii()` | `forest_visual.py` | done |
| P0-22 | 重写 `_render_dot()`（引用边样式） | `forest_visual.py` | done |
| P0-23 | 更新 `_enrich_svg_nodes()` | `forest_visual.py` | done |
| P0-24 | 更新 `_render_html()` | `forest_visual.py` | done |
| P0-25 | 更新 forest_visual 测试 | `test_forest_visual.py` | done |
| P0-26 | 更新前端 types (TreeNode) | `frontend/src/types/` | done |
| P0-27 | 更新前端 stores (trees 状态) | `frontend/src/stores/` | done |
| P0-28 | 重写 ConflictsPage | `frontend/src/pages/` | done |
| P0-29 | 更新 ForestViewer (tree-node 属性) | `frontend/src/components/` | done |
| P0-30 | 前端 Vitest 测试更新 | `frontend/src/__tests__/` | done |
| P0-31 | Python 全量回归测试 | all | done |
| P0-32 | 前端构建 + Vitest 全量 | all | done |
| P0-33 | 手动 E2E 验证 | all | pending |

---

## Phase P1: Backup 实现 ✅

补齐备份目录命名规则生成 + 循环防护 + workshop 时间源 + .kmmbakignore。

**设计文档**：`repo_memory/direct/DESIGN_P1_BACKUP.md`

| # | 任务 | 模块 | 状态 |
|---|------|------|------|
| P1-01 | `get_workshop_timeupdated()` 辅助函数 | `acf_parser.py` | done |
| P1-02 | acf_parser 扩展测试 | `tests/` | done |
| P1-03 | `get_workshop_backup_id()` 实现 | `backup_dir_builder.py` | done |
| P1-04 | `get_custom_backup_id()` 实现 | `backup_dir_builder.py` | done |
| P1-05 | `build_backup_dir()` 实现 | `backup_dir_builder.py` | done |
| P1-06 | `load_bakignore_rules()` 实现 | `backup_dir_builder.py` | done |
| P1-07 | builder 核心函数单元测试 | `tests/test_backup_dir_builder.py` | done |
| P1-08 | backup_ops 硬编码 kmmbackup_ 前缀过滤 | `backup_ops.py` | done |
| P1-09 | 循环防护测试 | `tests/test_backup_ops.py` | done |
| P1-10 | orchestrator.run() backup_dir 可选化 | `orchestrator.py` | done |
| P1-11 | CLI --backup-dir 可选化 | `cli.py` | done |
| P1-12 | Web API 适配 | `modmanager_web/*` | done |
| P1-13 | 前端适配 | `frontend/src/*` | done |
| P1-14 | 集成测试 | `tests/` | done |
| P1-15 | Python 全量回归 | all | done |
| P1-16 | 前端 Vitest + 构建 | all | done |

---

## Future（远期）

### P2: 引擎细节修复
- T1: same actionlist 中 delete→create 不产生 overwrite 警告
- 结点 vs 节点术语统一（代码变量名）

### P3: GUI 增强（待用户反馈）
- Forest 全部/仅分岔切换按钮
- M4: hover 高亮、拖拽选枝

### Forest Visualization Expansion（M3）
- Plot renderer
- trace/meta 扩展字段兼容验证

### GUI Visualization And Interaction（M4）
- hover 整链高亮
- 分叉节点超链接与详情展示
- 用户选枝 UI
- 插件运行链
- 老浏览器 fallback

### 其他
- 自定义脚本调用（危险操作，仅允许资深用户）
- base64 导入规则
- VDF/ACF 文件格式深度解析增强

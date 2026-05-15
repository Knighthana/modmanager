# 2026-05-14 工作日志（审计后）

## 审计对齐
- 审计报告阅读 + 提问 + 答复
- 文档清理残留（DESIGN_STORAGE/FOREST_MODEL/RULE_AGGREGATOR/REST_API）
- TERMS_FIELD_FREEZE 新增 4 字段
- DESIGN_REST_API status → partially-stable + 端点分组表
- workspace 字段命名 camelCase 统一

## Phase 5 — localStorage 聚合 + compute 仅接受 dict
- schemas.py: 删 aggregated_rule_path/kmm_rule_paths
- orchestrator.py: 仅用 aggregated_rule_set dict
- 前端 WorkspaceData 类型 + loadWorkspace/saveWorkspace

## GUI 界面完善
### 数据来源
- 标题对齐导航（📡 数据来源）
- 确认按钮移扫描旁，删除保存按钮
- 可见性 👀/🙈 emoji
- 路径列移最后，名称列加宽

### 规则概览
- 标题对齐导航（📋 规则概览）
- 预加载规则文件详情（展开前即显示）
- 规则文件元信息 i18n
- author 独立按钮 + popover 所有字段
- autoRestoreAggregated 路径比对
- GameNames 从 database 读取
- 查看源文件对话框

### 计算准备
- 标题对齐导航（🧮 计算准备）
- 重复高亮前端动态计算（勾选行）
- checkbox 影响高亮
- MOD 昵称从 aggregated_rule_set 读取
- 库表可见性/列顺序/合成库条目
- affected-entries 修复（前缀匹配 + 过滤 + 合成库）

### 森林可视
- 标题对齐导航（🌲 森林可视）
- 顶栏面板 + 底栏浮层状态条
- SVG 主动触发（onMounted + watch）
- compute 写入 forestStore（修复 SVG 不显示）
- minZoom 动态计算、maxZoom: 500
- 小地图 viewport 统一 scale

## 其他修复
- uiState 并入 workspace（audit_todo_future item 2）
- ConflictsPage workspace API → localStorage
- RulesOverviewPage workspace/save-inputs 删除
- `/api/api/` 双重前缀修复（5 个文件）
- Mock data/config.json 格式修复
- 前后端通信 7 个 bug 修复
- manual 模式缓存跳过（db_file 定义外提）
- steamlibpathstyle 语义修正（不猜测）
- pathstyle.normalize 加 from_style 参数
- workingPathstyle 前端删除（后端自动检测）
- validate_database appid 唯一性删除
- 文档增补：DESIGN_GUI.md DataSource/RulesOverview/ComputePrep/ForestPage 规则
- DESIGN_GUI_WORKSPACE.md workspace 结构 + uiState
- DESIGN_STEAM_DISCOVERY.md pathstyle 语义
- DESIGN_PATH_RESOLVER.md expand_path 规则

## TODO 完成记录（补充自 git 历史）

> 以下条目在 `work_memo/states.md` 中已勾选，此处按 git commit 逐一归档。

### TODO-54 工具文件治理
- **裁定**：user_config 由 first_use 自动创建；database 由扫描写入；wsl_steam_scan.log 由 `tools/test_wsl_crossover.py` 产生
- **commit** `7b83b7a` (05-08)：`test_wsl_crossover.py` 移入 `tools/`；删除可再生 `wsl_steam_scan.log`
- **commit** `182c27b` (05-13 Phase 1)：`bootstrap.py` 实现单级搜索 + first_use 自动创建 user_config；`generate_database` 使用 `databases[name].path` 写入

### TODO-56 刷新后 Database 数据丢失
- **commit** `90e0b38` (05-13 Phase 4)：`DataSourcePage` / `AdvancedPage` / `ForestPage` 的 `onMounted` 自动调用 `POST /api/database/read` 恢复数据
- **验证**：页面刷新后 Database 数据不再丢失

### TODO-57 manual 模式缓存返回旧数据
- **commit** `90e0b38` (05-13 Phase 4)：`bootstrap.py` 中 manual 模式跳过缓存（`db_file` 定义外提），强制重新扫描
- **补充提及**：`after_audit` §其他修复 第 1 条

### TODO-58 GUI-P0 扫描模式语义修复（仅自动/全部/仅手动参数映射）
- **commit** `2179c19` (05-15)：`frontend/src/stores/datasource.ts`
  - `greedyParsing` → `greedy_parsing`（统一 snake_case 参数映射）
  - 扫描模式语义整理：auto 模式带/不带 paths；manual 模式强制 paths
- **影响文件**：1 文件，~5 行

### TODO-59 GUI-P0 compute 参数契约统一（aggregated_rule_set）
- **commit** `2179c19` (05-15)：`frontend/src/stores/forest.ts`、`frontend/src/types/index.ts`、测试文件 ×4
  - `PipelineParams.kmm_rule_paths` → `aggregated_rule_set: Record<string, unknown>`
  - `runPipeline()` / `computeOnly()` 构建请求时仅传 `aggregated_rule_set`，不再传 `kmm_rule_paths`
  - `lastSuccessfulParams` 中同步替换
- **影响文件**：8 文件，+52/−102 行

### TODO-60 GUI-P0 计算结果计数字段对齐（避免 0 树 0 映射假成功）
- **commit** `2179c19` (05-15)：`frontend/src/pages/ComputePrepPage.vue`
  - 不再信任后端 `trees_count` / `mapping_count` 字段
  - 改为 `Array.isArray(result.data.trees) ? result.data.trees.length : 0`
  - 同理处理 `final_mapping`
  - 响应类型从 `trees_count?: number` 改为 `trees?: unknown[]`

### TODO-61 GUI-P0 ForestPage 职责边界修复（移除计算/运行触发）
- **commit** `2179c19` (05-15)：`frontend/src/pages/ForestPage.vue`
  - 删除 `onCompute()` / `onRun()` / `prepareParams()` 三个函数（~70 行）
  - 删除 `DatabaseSelector` 组件引用和 `<DatabaseSelector>` 模板
  - 删除顶栏"计算"/"运行"两个按钮
  - ForestPage 降级为纯展示页（计算触发已在 ComputePrepPage）

### TODO-62 GUI-P1 Settings database rename/delete 同步 workspace（perDatabase 迁移/清理）
- **commit** `e4487e9` (05-15)：`frontend/src/pages/SettingsPage.vue`、`SettingsPage.test.ts`
  - 新增 `syncWorkspaceDatabases(currentDbKeys)` — 重命名时迁移 `perDatabase[旧key]` → `perDatabase[新key]`；删除时清理对应 entry；更新 `lastDatabase`
  - 新增 `databaseRenameMap` — 编辑 database key 时记录旧→新映射
  - `removeDbKey()` 同步清理 renameMap
  - **附带清理**：删除未使用的 `frontend/src/stores/workspace.ts`（263 行）
  - **测试**：+64 行（rename/delete 后 workspace 同步验证）

### TODO-63 GUI-P1 AdvancedPage 三标签自动刷新一致性（database/aggregated/userConfig）
- **commit** `7c0fb2f` (05-15)：`frontend/src/pages/AdvancedPage.vue`
  - `watch(activeTab)` 从"仅 database 标签刷新"改为"所有标签切换均触发 `refreshTab(newVal)`"
  - **测试**：新增 `AdvancedPage.test.ts`（106 行），覆盖 database/aggregated/userConfig 三标签自动刷新

### TODO-64 GUI-P1 页面视觉一致性基线（标题/按钮圆角/表格行高/卡片节奏）
- **commit** `ed440ae` (05-15)：新增 `frontend/src/styles/gui-consistency.css`（36 行 CSS 变量）
  - `--gui-title-size: 24px`、`--gui-title-weight: 650`、`--gui-title-margin: 0 0 18px 0`
  - `--gui-button-radius: 8px`（大按钮）、`6px`（小按钮）
  - `--el-table-row-height: 40px`
  - `--gui-card-gap: 16px`、卡片圆角 `10px`
  - 8 个页面根元素统一添加 `class="gui-page"`
  - `main.ts` 全局引入 CSS

### TODO-65 GUI-P1 文档冻结同步（workspace 单写入口 / Advanced 刷新策略 / 键模型）
- **commit** `277c0c2` (05-15)：`repo_memo/DESIGN_GUI.md`、`DESIGN_GUI_WORKSPACE.md`
  - workspace 键模型统一为 `modmanager:workspace.perDatabase[name]`（消除旧的 `decisions:{name}` 等分散 key 格式残留）
  - 明确 `persistence.ts` 的 `loadWorkspace/saveWorkspace` 为唯一写入口；标注 `workspace.ts` store 已移除
  - Advanced 刷新策略写入文档
  - 同步更新 D2/D6/D8 决策记录的持久化路径引用

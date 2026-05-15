# 工作状态

## 进行中：工作区模型重构（TODO-71）

> 裁定文档：`work_memo/2026-05-16_workspace_model_decisions.md`
> 新设计文档：`repo_memo/DESIGN_WORKSPACE_MODEL.md`（待写）
> 目标：工作区是先行容器（而非计算后产物），中枢式页面流，全量 URL 重构

### Phase 1 — 文档
- [x] TODO-W1: 新建 `repo_memo/DESIGN_WORKSPACE_MODEL.md`
- [x] TODO-W2: 更新 `repo_memo/DESIGN_STORAGE.md`（workspace 路径、user_config.workspace_dir）
- [x] TODO-W3: 更新 `repo_memo/DESIGN_REST_API.md`（URL 全量重构）
- [x] TODO-W4: 更新 `repo_memo/DESIGN_GUI_WORKSPACE.md`（页面流重排 → superseded 存根）
- [x] TODO-W5: 更新 `repo_memo/DESIGN_ORCHESTRATOR.md`（新增 workspacemanager 下属）
- [x] TODO-W6: 更新 `repo_memo/TERMS_FIELD_FREEZE.md`（新字段 + 废弃字段）
- [x] TODO-W7: 归档 `repo_memo/DESIGN_SVG_CACHE_AND_FOREST_LIST.md`

### Phase 2 — 后端
- [x] TODO-W8: 新建 `src/modmanager/core/workspacemanager.py`（工作区 CRUD + 文件读写）
- [x] TODO-W9: 新建 `src/modmanager_web/routes/workspace.py`（工作区端点：create/delete/list）
- [x] TODO-W10: 改造 `src/modmanager_web/routes/pipeline.py`（URL 加 workspace_id，集成 workspacemanager）
- [x] TODO-W11: 改造 `src/modmanager_web/routes/rules.py`（聚合结果存入工作区）
- [x] TODO-W12: 改造 `src/modmanager_web/routes/database.py`（降为纯 database 管理，与工作区解耦 — 已有代码已满足）
- [x] TODO-W13: 改造 `src/modmanager_web/routes/config.py`（新增 workspace_dir 字段 — SaveConfigRequest 已接受任意 config dict）
- [x] TODO-W14: 更新 `src/modmanager_web/schemas/`（新增 workspace 相关 schema）
- [x] TODO-W15: 更新 `src/modmanager/orchestrator.py`（集成 workspacemanager 下属）

### Phase 3 — 前端
- [x] TODO-W16: 前端路由拓扑重排（中枢式：工作区列表为默认首页）
- [x] TODO-W17: 新建 `src/pages/WorkspaceListPage.vue`（工作区列表页：创建/删除/进入）
- [x] TODO-W18: 改造 `src/pages/ComputePrepPage.vue`（工作区上下文，加"计算并查看"按钮）
- [x] TODO-W19: 改造 `src/pages/ForestPage.vue`（改为接收 workspace_id，纯查看器）
- [x] TODO-W20: 改造 `src/pages/RulesOverviewPage.vue`（工作区上下文内聚合）
- [x] TODO-W21: 改造 `src/pages/DataSourcePage.vue`（降为纯 database 管理）
- [x] TODO-W22: 清理浏览器存储（淘汰 `modmanager:workspace`；sessionStorage 主读 + localStorage 留档）

### Phase 4 — 清理与验证
- [x] TODO-W23: 删除旧 `workspace.py` 残留（经确认无残留文件，旧 workspace 端点已在方案 B 阶段删除）
- [ ] TODO-W24: 更新 tests（前端 14 个测试待适配新模型）
- [ ] TODO-W25: 全链路验证（创建工作区 → 聚合规则 → 计算 → 查看森林 → 删除工作区）

---

## 存量待办

- [ ] （挂起）TODO-10: 前端空输入校验
- [ ] （待讨论）TODO-51: 统一界面视觉
- [ ] （待讨论）TODO-52: 主题切换
- [ ] （待讨论）TODO-53: 日志文件整洁
- [ ] TODO-66: 规则概览 — preview 图片加载（外部资源，需白名单机制）
- [ ] TODO-67: 规则概览 — README 文件内容查看（外部资源，需白名单机制）
- [ ] TODO-68: 规则概览 — author 字段的键含义与展示方式待讨论
- [ ] TODO-69: `inputs_hash` 实现不完整
- [ ] TODO-70: 森林图展示打磨（小地图比例/滚动条/放缩）— 独立任务，不随 TODO-71 完成
- [x] TODO-71: trees 到底存哪 — **已完成。工作区模型落地，trees/mapping/SVG 存工作区目录**

### 可延后（来自 audit_todo_future.md）
- [ ] `useWorkspaceStore` 唯一写者
- [ ] `activeTab` / `sidebarCollapsed` 迁入 uiState
- [ ] 前端 Transport Abstraction（`src/api/transport.ts`）

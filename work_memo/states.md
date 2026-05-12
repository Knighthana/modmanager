# 工作状态

> 执行计划详见 `repo_memo/DESIGN_EXECUTION_PLAN.md`

- [x] TODO-15: ✅ 自适应宽度缩放 + svg-pan-zoom 迁移 + 重置按钮 + 小地图
- [x] TODO-21: ✅ "发现模式"偏好保存在前端持久化（被新方案取代，已清除）
- [ ] （挂起）TODO-10: 空输入校验
- [ ] （挂起）TODO-19: 重复 radio 视觉提示——计算准备页中重复 appid/mixed_id 行柔和高亮
- [ ] TODO-28R: 【重定义·清退】清退 localStorage 中业务数据 → 删除 datasource / datasource-db / forest-store 三个 key 及读写代码（Phase 2）；persistence.ts 仅保留 UI 状态
- [ ] TODO-30: mock-first 策略定稿 ✅（DESIGN_MOCK_INFRA.md 已完成）
- [ ] TODO-32: 后端 workspace state 设计 → ✅（DESIGN_WORKSPACE_STATE.md 已完成）；实现 workspace.json + 4 个 REST API（status / save-inputs / save-decisions / save-results）（Phase 1）
- [ ] TODO-33: persistence.ts 职责重定义 → 仅限纯 UI 状态；save/load 失败时 notify 警告
- [ ] TODO-41: managed 语义迁移 → database.json 移除 managed/warnings/errors；managed_entries 改为 compute 可选参数（列表格式）（Phase 1）
- [ ] TODO-27R: 前后端数据流一致性审查 → compute 端点不接受 database dict（接受 database_path + 可选 managed_entries）（Phase 1）
- [ ] TODO-35: 搭建 MSW mock 基础设施 → frontend/src/mocks/；npm run dev:mock / npm run dev（Phase 3）
- [ ] TODO-36: 实现后端 workspace state 存储 + REST API（Phase 1）
- [ ] TODO-42: 【新】新增 `POST /api/rules/affected-entries` 端点 → 供计算准备页查询被引用条目（Phase 1.9）
- [ ] TODO-38: SettingsPage mock-first 重写 → 管理 user_config + Database JSON 编辑（Phase 3）
- [ ] TODO-39: OperationsPage mock-first 实现 → 映射摘要 + 操作按钮（backup/apply/restore）（Phase 3）
- [ ] TODO-40: RulesOverviewPage mock-first 实现 → 规则选择 + 详情 + [保存规则选择]（Phase 3）
- [ ] TODO-43: 【新】计算准备页 mock-first 实现 → 受影响条目表格 + checkbox 预选 + [▶ 开始计算] + [查看结果]（Phase 3）
- [ ] TODO-22: 三项迁移 → ForestPage 字段迁出（Phase 4）
- [ ] TODO-20: 选项卡解耦 → 六页面独立（Phase 4）
- [ ] TODO-23: user config 路径迁入设置页 + 启动导航（Phase 4）
- [ ] TODO-24: backup dir 语义澄清（Phase 4）
- [ ] TODO-26: "手动路径"→"手动路径列表"（Phase 4）
- [ ] TODO-29: Settings Database JSON 保存按钮修复（Phase 4）
- [ ] TODO-31: Forest 小地图点击定位修复 + 窗口大小调整（Phase 4）

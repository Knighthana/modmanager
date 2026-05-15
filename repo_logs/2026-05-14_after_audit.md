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

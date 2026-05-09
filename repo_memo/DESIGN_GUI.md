# DESIGN_GUI — 前端 GUI 设计

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 规定前端 GUI 的总体架构、交互边界与页面级设计原则
> 来源：DESIGN_PHASE3_GUI.md + DESIGN_P3_GUI2.md + DESIGN_GUI_CONVENTIONS.md（合并）
> 创建：2026-05-08
> 更新：2026-05-09 — 补充 §二.3 分支决策持久化（TODO-8）、§三.1 onDbPathBlur 校验（TODO-9）
> 更新：2026-05-09 — 重构 Tab 结构（7 页）、新增 RulesOverviewPage + SettingsPage 设计、DataSource 职责扩展
> 更新：2026-05-09 — 新增 §选项卡解耦原则（TODO-20）、§字段归属迁移（TODO-22/25）

---

## 一、Phase 3 总设计（DESIGN_PHASE3_GUI.md）

> **维护说明**：本文档保留了 Phase 3 的设计来源，但当前仍作为 GUI 总体设计的现行文档使用。
> 其中 §4 的 `ForestNode` 类型在 P0 后已改为 `TreeNode`（新增 `root_path` / `refs` / `resolved_state`）；涉及森林输出结构时，以 `repo_memo/DESIGN_FOREST_MODEL.md` 和实际类型定义为准。

### 决策汇总

| Q# | 决策 |
|-----|------|
| Q1 | **Vue 3** |
| Q2 | **M3 先独立完成**（静态 HTML 可视化），Phase 3 再交互 GUI |
| Q3 | **方案 A** — 前端构建产物嵌入 FastAPI 静态文件 |
| Q4 | Forest 可视化 → 冲突裁决 → 规则浏览器 → 备份控制台 |
| Q5 | **先最小集**（表格 + 按钮 + SVG zoom/pan），逐步完整 |
| Q6 | **REST + SSE** |
| Q7 | **仅 localhost** |
| Q8 | **npm + Vite + TypeScript** |
| Q9 | **`frontend/`**（项目根目录） |
| Q10 | **后端渲染 SVG** → API 返回 → `v-html` 插入 DOM → `svg-pan-zoom` 接管缩放/平移 → 事件委托交互 |
| Q11 | **Element Plus** |
| Q12 | **SPA + Vue Router** |
| Q13 | **Pinia** — `useForestStore` 集中管理 pipeline 结果 |
| Q14 | Tab 职责划分 | 7 页：数据源→规则概览→设置→Forest→冲突→操作→规则制定（dumb） |

### 架构总览

```
                         ┌──────────────────────────────────┐
                         │          frontend/                │
                         │   Vue 3 + Vite + TypeScript       │
                         │   Element Plus + Pinia            │
                         │   ┌──────────┐  ┌─────────────┐  │
     浏览器 ──(HTTP)──────→│  │ Vue      │  │  SSE Client │  │
                         │  │  Router   │  │  (fetch+流)  │  │
                         │  └────┬─────┘  └─────────────┘  │
                         │       │                          │
                         │  ┌────▼──────────────────────┐   │
                         │  │         Pinia Store         │   │
                         │  │  useForestStore             │   │
                         │  │  usePipelineStore           │   │
                         │  └────────────────────────────┘   │
                         └────────────────┬─────────────────┘
                                          │ Vite build
                         ┌────────────────▼─────────────────┐
                         │  src/modmanager_web/static/       │
                         │  (构建产物 → FastAPI StaticFiles) │
                         └────────────────┬─────────────────┘
                                          │
                         ┌────────────────▼─────────────────┐
                         │       modmanager_web (FastAPI)    │
                         │  GET  /api/*    (REST endpoints)  │
                         │  POST /api/*    (SSE endpoints)   │
                         │  GET  /*        (SPA fallback)    │
                         └────────────────┬─────────────────┘
                                          │ import
                         ┌────────────────▼─────────────────┐
                         │       modmanager              │
                         │  orchestrator / engine / ...      │
                         └──────────────────────────────────┘
```

### 目录结构

```
frontend/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html                   ← SPA 入口
├── src/
│   ├── main.ts                  ← Vue 应用启动
│   ├── App.vue                  ← 根组件（layout + router-view）
│   ├── router/
│   │   └── index.ts             ← Vue Router 配置
│   ├── stores/
│   │   ├── forest.ts            ← useForestStore (Pinia)
│   │   └── datasource.ts        ← useDataSourceStore
│   ├── pages/
│   │   ├── ForestPage.vue       ← Forest 可视化嵌入
│   │   ├── ConflictsPage.vue    ← 冲突裁决 UI
│   │   ├── RulesPage.vue        ← 规则浏览器
│   │   ├── BackupPage.vue       ← 备份/恢复控制台
│   │   └── DataSourcePage.vue   ← 数据源发现面板
│   ├── components/
│   │   ├── LayoutShell.vue      ← 全局布局
│   │   ├── ForestViewer.vue     ← SVG 渲染 (svg-pan-zoom) + hover/click 交互 + 小地图 + 重置按钮
│   │   ├── ConflictPanel.vue    ← 冲突列表 + 候选选择
│   │   ├── SseStatusBar.vue     ← SSE 进度条
│   │   └── ...
│   ├── api/
│   │   ├── client.ts            ← fetch 封装
│   │   ├── sse.ts               ← SSE 流式读取
│   │   └── notify.ts            ← 平台解耦通知
│   ├── utils/
│   │   ├── persistence.ts       ← 抽象存储层
│   │   ├── paths.ts             ← 路径工具
│   │   └── scroll.ts            ← 滚动工具
│   ├── types/
│   │   └── index.ts             ← TypeScript 类型定义
│   └── errorCodes.ts            ← 错误/警告代码映射
```

### Vue Router 设计

七页面结构，一个 layout shell。

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 重定向 | → `/datasource` |
| `/datasource` | DataSourcePage | 数据源：Steam 扫描、database 管理、规则文件扫描、user_config 发现 |
| `/rules-overview` | RulesOverviewPage | 规则概览：展示当前 rule 与 database 中被覆盖的 game/mod 清单（方案A） |
| `/settings` | SettingsPage | 设置：管理 user_config.json |
| `/forest` | ForestPage | Forest 可视化（仅计算映射，不执行 backup/apply） |
| `/conflicts` | ConflictsPage | 冲突裁决 |
| `/operations` | OperationsPage | 备份/应用/恢复操作 |
| `/rule-editor` | RuleEditorPage | 规则制定（dumb 占位，远期功能） |

### 选项卡解耦原则（TODO-20）

各选项卡应尽可能**独立设计**，避免通过共享 store 状态产生隐式耦合：

| 原则 | 说明 |
|------|------|
| **单向数据流** | 上游选项卡产出数据 → 下游选项卡消费。不做反向依赖 |
| **传递边界明确** | 选项卡间通过 router params / store 快照传递，不通过实时双向绑定 |
| **各自可独立渲染** | 任一选项卡在缺少上游数据时，应显示明确的空状态提示，而非崩溃或假死 |
| **store 读写分离** | 每个选项卡只写自己负责的 store 字段，只读上游选项卡写入的字段 |

### 字段归属迁移（TODO-22 / TODO-25）

当前 ForestPage 上的以下字段需迁出：

| 字段 | 当前位置 | 目标选项卡 |
|------|----------|-----------|
| Database 路径输入框 | ForestPage | **数据源**（DataSourcePage） |
| Database JSON 编辑区 | ForestPage | **数据源**（DataSourcePage） |
| Rule paths 选择 | ForestPage | **数据源**（DataSourcePage） |
| dry run 开关 | ForestPage | **文件操作**（OperationsPage） |
| "应用流水线"按钮 | ForestPage | **文件操作**（OperationsPage） |
| backup dir 输入框 | ForestPage | 移除——backup dir 由 `build_backup_dir()` 自动推导（见 DESIGN_BACKUP.md） |

ForestPage 迁出后仅保留：**计算映射**按钮 + SVG 可视化面板。

### Element Plus 组件映射

| UI 元素 | Element Plus 组件 |
|----------|-------------------|
| 全局布局 | `el-container` + `el-aside` + `el-main` |
| 导航菜单 | `el-menu` (vertical, collapse) |
| 参数表单 | `el-form` + `el-input` + `el-switch` + `el-button` |
| 进度条 | `el-progress` / `el-alert` |
| 冲突列表 | `el-table` + `el-tag` |
| 候选选择 | `el-radio-group` |
| 统计卡片 | `el-card` + `el-statistic` |
| 文件列表 | `el-tree` / `el-table` |
| 按钮操作 | `el-button` (primary/danger) |
| 通知 | `ElNotification` / `ElMessage` |
| 加载 | `v-loading` directive |
| Badge | `el-badge`（冲突数量红点） |

### 规则概览页（RulesOverviewPage）

**定位**：在干净的 database 与选中的 rule 之间，展示覆盖关系，让用户确认无误后再进入 Forest 计算。

**展示内容**（方案 A——从 rule 出发）：
- 顶部：当前选中的 rule 文件列表（文件名 + nickname）
- 主体：rule 中定义的所有 `mixed_id` 列表
  - 对每个 mixed_id，标注在 database 中是否有对应条目
  - 有对应：显示 game 名称、mod 路径、managed 状态
  - 无对应：标记"缺失"，提示该 mod 未安装
- 辅助：rule 文件的 `nickname`、`preview`、`readme` 信息
- 底部：确认按钮 → 将确认后的 database + rules 传入 Forest 页

**约束**：
- 本页为纯展示+确认，不做任何写操作
- 缺失的 mixed_id 高亮警告但不阻断流程（用户可选择忽略并继续）
- 从 DataSource 页传入干净的 database（所有 managed 标记已正确设置）

### 设置页（SettingsPage）

**定位**：user_config.json 的可视化管理界面。

**展示/编辑字段**：
- `bakprefix`：备份目录名前缀（可编辑，默认 `kmmbackup_`）
- `bakignore`：备份忽略模式列表（可增删）
- `database_output_path`：database.json 输出路径（可编辑）
- `aggregated_ruleset_output_path`：aggregated_rule_set.json 输出路径（可编辑）

**行为**：
- 加载时从后端 `POST /api/config/discover` 获取当前配置
- 用户修改后点击"保存"，调用 `POST /api/config/save`
- 保存成功显示提示，失败显示错误详情

### 实现顺序

```
Task 15: frontend/ 脚手架
Task 16: M3 前置：forest_visual.py SVG 升级
Task 17: api/ 层（client.ts + sse.ts）
Task 18: stores/forest.ts
Task 19: router + LayoutShell
Task 20: ForestPage + ForestViewer
Task 21: ConflictsPage
Task 22: RulesPage
Task 23: BackupPage
Task 24: app.py 更新（静态文件 mount + SPA fallback）
Task 25: 测试
```

---

## 二、M4 交互增强（DESIGN_P3_GUI2.md）

### 现有能力

| 能力 | 状态 |
|------|------|
| zoom/pan（svg-pan-zoom 库接管，viewBox 操作）| ✅ |
| pending 树点击跳转 ConflictsPage | ✅ |
| 冲突裁决（ConflictsPage 表格单选）| ✅ |
| SVG 结点属性：`data-tree-node`、`data-tree-pending` | ✅ |
| 引用边渲染（虚线）| ✅ |
| `resolved_state` 着色（pending→红、deleted→灰等）| ✅ |
| 自适应容器宽度（fit + resize）| ✅ |
| 容器高度匹配缩放后 SVG（无纵向空白）| ✅ |

### 新增功能

#### 0. ForestViewer 渲染方案

**方案选型**：从 CSS `transform: scale() translate()` 迁移为 `svg-pan-zoom` 库（操作 SVG `viewBox`）。

| 维度 | 旧方案 (CSS transform) | 新方案 (svg-pan-zoom) |
|------|----------------------|----------------------|
| 缩放方式 | `transform: scale()` 作用于包裹 div | 直接操作 SVG `viewBox` |
| 渲染质量 | 非整数倍缩放模糊 | 始终矢量锐利 |
| 事件坐标 | 需手动换算 | 原生 SVG 坐标系 |
| 缩放/平移 | 手写 ~100 行 | 库内置 |
| 自适应容器 | 手写 fitToContainer + ResizeObserver | `fit: true` + `resize()` |

**新增功能**：

- **重置视图按钮**：容器上方工具栏，调用 `fit()` + `center()` 恢复初始状态
- **小地图**：左上角 180×120px 半透明浮动窗，矩形表示全图区域 + 蓝色视口框
  - 全图区域矩形：浅灰底 + 边框，标示 SVG viewBox 整体范围
  - 视口矩形：蓝色半透明，标示当前可见区域
  - 可点击：点击小地图任意位置 → 主视图 pan 到对应位置
  - 视口框实时同步主视图的 pan/zoom 状态
  - 后续可选：用户自定义显示位置或隐藏

#### 1. hover 整链高亮

**行为**：鼠标悬停在一棵树（含结点 + 边）上时，高亮：
- 该树本身
- 该树引用的所有树（`refs`）
- 引用该树的所有树（`referenced_by`）

其他树变暗（opacity 降低）。

**后端改动**（`forest_visual.py`）：
- SVG 结点新增 `data-tree-refs` 和 `data-tree-referenced-by` 属性

**前端改动**（`ForestViewer.vue`）：
- 通过事件委托处理 hover，高亮相关节点及其边

#### 2. 点击选枝

**行为**：点击 pending 树 → 进入"选中"模式（蓝色边框高亮）→ 点击通向该树的边 → 产生决策。

**阶段 A**（已实现）：点击 pending 树选中，点击高亮边/源结点调用 `setDecision`，自动刷新可视化。

**阶段 B**（后续可选）：真正拖拽（drag & drop）。

#### 3. 分支决策持久化（TODO-8）

**问题**：用户在 ConflictsPage 做出的分支决策（`branch_decisions`）仅保存在页面本地状态，刷新或切换页面后丢失。

**方案**：
- 在 `ForestStore` 中新增 `branchDecisions: Record&lt;string, string&gt;` 响应式状态（key=`root_path`，value=选中源的 `root_path`）
- `setDecision()` action 同时写入 store
- ConflictsPage 的 `branchDecisions` 从 store 读取，不再依赖页面本地 computed
- `reset()` 不清除 `branchDecisions`——与 `lastSuccessfulParams` 同级保留
- 组件挂载时从 store 恢复已有决策到 UI 选中状态

**涉及文件**：
- `frontend/src/stores/forest.ts` — 新增 `branchDecisions` 状态 + `setDecision` action
- `frontend/src/pages/ConflictsPage.vue` — 改为从 store 读取/写入
- `frontend/src/__tests__/` — 补充持久化回归测试

### 测试策略

| # | 测试 | 说明 |
|---|------|------|
| T1 | `test_svg_has_refs_attribute` | SVG 结点有 `data-tree-refs` |
| T2 | `test_svg_has_referenced_by` | SVG 结点有 `data-tree-referenced-by` |
| T3-T6 | 前端 hover/click 交互测试 | 高亮、选枝模式、决策 |

---

## 三、GUI 行为约定（DESIGN_GUI_CONVENTIONS.md）

### 1. ForestPage — Database 路径行

**布局**：
```
[el-form-item label="Database 路径"]
  [el-input (flex:1)]   [ℹ️ popover]   [按钮]
```

**锁定/解锁语义**：
| 状态 | 输入框 | 按钮 | 点击效果 |
|------|--------|------|---------|
| 锁定 | disabled，灰色 | "手动填写" | 解锁 → 可写 |
| 解锁 | editable，白色 | "使用自动" | 锁定 → 恢复自动值 |

**onDbPathBlur 校验（TODO-9）**：

Database 路径输入框失焦（blur）时触发路径解析，不得静默失败：

1. 调用后端 `POST /api/database/load` 尝试加载路径指向的 `database.json`
2. **加载成功** → 更新 `storedDatabase`，自动切换回锁定状态，输入框显示解析后的规范路径
3. **加载失败** → 显示错误气泡（复用 `notify.ts` / `errorCodes.ts`），**保留用户输入不清空**
4. 用户可在看到错误后修正路径，再次失焦触发重试

约束：
- 校验失败**必须**给出可见的用户反馈，不得静默忽略
- 校验期间不阻塞 UI（异步执行）
- 空输入不触发校验

### 2. prepareParams 数据库优先级

```typescript
// 优先级 1: Database JSON 非空
if (databaseJson.trim()) → JSON.parse(databaseJson)
// 优先级 2: 自动模式 + storedDatabase 存在
else if (!dbManualOverride && storedDatabase) → storedDatabase（dict）
// 优先级 3: 手动模式 + databasePath 非空
else if (dbManualOverride && databasePath) → databasePath（str）
// 优先级 4: 无数据
else → {}
```

### 3. 错误/警告提示系统

- `notify.ts` — 平台解耦的弹出通知（当前:浏览器 DOM popup，预留: Tauri）
- `errorCodes.ts` — 错误/警告代码 → 人类可读说明的映射
- 错误/警告条目可点击 → 弹出气泡

### 4. 路径显示规范

- 所有 GUI 表格中目录路径显示必须以 `/` 结尾
- 使用 `ensureTrailingSlash(path)` 工具函数（`utils/paths.ts`）

### 5. 侧边栏品牌

- 格式：`🔧 Knighthana's Mod Manager`
- 样式：粗体 800，14px，底部有分割线

### 6. ForestStore reset() 边界

`reset()` 仅清空**输出字段**（trees、errors、warnings、finalMapping 等），保留**输入字段**（storedDatabase、pipelineForm、dbManualOverride、userConfig）。

### 7. 决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | Database 输入形式 | pipeline 端点同时接受 dict 和路径字符串 |
| D2 | 通知系统 | `notify.ts` 平台解耦抽象层 |
| D3 | 错误说明 | 点击条目弹出气泡 |
| D4 | 路径显示 | 目录路径统一以 `/` 结尾 |
| D5 | reset() 范围 | 只清输出不清输入 |
| D6 | prepareParams 优先级 | JSON > storedDatabase dict > path string > {} |

---

## 附录：警告说明参考

| 警告码 | 说明 | 对结果的影响 |
|--------|------|-------------|
| `W_LOCAL_MOD_MISSING` | 规则引用的 mod 未安装 | 对应条目被跳过 |
| `W_NO_SOURCE_MATCH` | mod 源文件不存在 | 对应条目被跳过 |
| `W_MISSING_SOURCE_ROOT` | 缺少源 mod 根目录 | 对应操作被跳过 |
| `W_MISSING_DEST_ROOT` | 缺少目标 mod 根目录 | 对应操作被跳过 |
| `W_CREATE_TARGET_EXISTS_OVERWRITE` | create 目标已存在 | 执行时被覆盖 |
| `W_SOURCE_DELETED` | 树引用的源被删除 | 引用树操作被跳过 |
| `W_SOURCE_DIRECTORY_DELETED` | 源文件的祖先目录被删除 | 引用树操作被跳过 |
| `W_FOREST_BRANCHING` | 树有多个有效操作竞争 | 需手动选择 |
| `W_NO_VALID_OPERATION` | 树的所有操作都失效 | 不进入 final_mapping |
| `W_FOREST_BRANCHING_UNRESOLVED` | 存在未决议的分枝树 | final_mapping 可能被清空 |
| `W_EMPTY_ACTIONLIST_AFTER_FILTER` | 某 mod 的所有 action 被过滤 | 该 mod 不产生映射 |
| `W_DESTIN_NONE_SKIPPED` | action 的 destin 为 "none" | 该 action 被跳过 |
| `W_PATH_TRAILING_SLASH_FIXED` | 目录路径缺 `/` | 已由聚合器自动补全 |

## 附录：术语规范

| 中文 | 含义 | 示例 |
|------|------|------|
| **树** | 独立根的 ForestTree 实例 | 树 A 引用了树 B |
| **根** | 树的根路径（文件路径）| root_path |
| **结点** | 树/图上的元素 | Forest 有 892 个结点 |
| **节点** | 具备计算能力的实体 | 服务器节点 |
| **分枝** | 同一树根有多个竞争操作 | 冲突分枝 |
| **引用** | 树之间的依赖边 | 树 A 引用树 B |
| **映射** | 从 rule action 到文件路径的解析结果 | final_mapping |
| **流水线** | 聚合→计算→备份→应用的完整流程 | pipeline run |

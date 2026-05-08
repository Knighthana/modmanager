# DESIGN_GUI — 前端 GUI 设计

> 状态：DRAFT
> 来源：DESIGN_PHASE3_GUI.md + DESIGN_P3_GUI2.md + DESIGN_GUI_CONVENTIONS.md（合并）
> 创建：2026-05-08

---

## 一、Phase 3 总设计（DESIGN_PHASE3_GUI.md）

> **注**：本文档为 Phase 3 实现时的历史设计快照。
> §4 中的 `ForestNode` 类型在 P0 后已改为 `TreeNode`（新增 `root_path`/`refs`/`resolved_state`）。
> 当前权威规范以实际代码为准。

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
| Q10 | **后端渲染 SVG** → API 返回 → `v-html` + 事件委托交互 |
| Q11 | **Element Plus** |
| Q12 | **SPA + Vue Router** |
| Q13 | **Pinia** — `useForestStore` 集中管理 pipeline 结果 |

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
│   │   ├── ForestViewer.vue     ← SVG 渲染 + zoom/pan 交互
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

四个页面（后扩展为五个），一个 layout shell。

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 重定向 | → `/forest` |
| `/forest` | ForestPage | Forest 可视化 |
| `/conflicts` | ConflictsPage | 冲突裁决 |
| `/rules` | RulesPage | 规则管理 |
| `/backup` | BackupPage | 备份恢复 |
| `/datasource` | DataSourcePage | 数据源发现 |

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
| zoom/pan（滚轮缩放 + 拖拽平移）| ✅ |
| pending 树点击跳转 ConflictsPage | ✅ |
| 冲突裁决（ConflictsPage 表格单选）| ✅ |
| SVG 结点属性：`data-tree-node`、`data-tree-pending` | ✅ |
| 引用边渲染（虚线）| ✅ |
| `resolved_state` 着色（pending→红、deleted→灰等）| ✅ |

### 新增功能

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

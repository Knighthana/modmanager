# Phase 3 — 前端修正

> Status: plan
> Authority: arch
> Created: 2026-05-14
> Source: `work_memo/2026-05-14_decisions.md`（vFinal 方案 B）+ Phase 1/2 产物
> 前置：Phase 1+2 已完成。全部 Python test 通过。后端已无 workspace 端点。

---

## Task 3.0: 清理与准备

### 3.0.1 删除 workspace MSW mock handlers
- 检查 `frontend/src/mocks/handlers/` 中是否有 workspace 相关 handler
- 如有 → 删除

### 3.0.2 检查前端类型定义
- `frontend/src/types/` 中是否有 workspace 相关类型 → 删除
- 是否有 `database_path`、`user_config_path` 等旧字段 → 删除

---

## Task 3.1: `stores/datasource.ts`

### 删除
- `databaseOutputPath` 状态字段（第 18 行及相关引用）
- `scan()` 中的 `cache_path` 传参

### 新增/修改
- `scan()` 中：新增 `database_name?: string` 参数（默认 "default"），传入请求

---

## Task 3.2: `stores/forest.ts`

### 删除
- `pipelineForm.databasePath`（第 55 行）— 不再需要
- `pipelineForm.databaseJson`（第 56 行）— 死代码
- `pipelineForm.userConfigPath`（第 60 行）— 后端自己知道
- `pipelineForm.cachePath`（第 63 行）— 已删除
- `pipelineForm.discoveryMode`、`pipelineForm.manualSteamPath` — 这些字段保留，但不通过 workspace 持久化
- `initFromWorkspace()` 函数 — 不再有 workspace
- `watch` 自动同步 `pipelineForm` 到后端的逻辑（第 309-321 行）
- 所有 `apiPost('/workspace/*')` 调用

### 修改
- `discoverDatabase()`：传 `database_name` 而非 `cache_path`
- `computeOnly()` / `runPipeline()`：传 `database_name`、`managed_entries`、`branch_decisions` 作为请求参数
- `pipelineForm` 新增 `databaseName: string = "default"`

### 新增
- 从 localStorage 读/写 decisions 和 results 的 utility 方法（可复用 persistence.ts）

---

## Task 3.3: 新增 `components/DatabaseSelector.vue`

### 职责
公共下拉组件。在所有涉及 database 操作的页面显示。

### Props
无（数据从后端 API 加载）

### 行为
```
onMounted:
  GET /api/config/discover → 拿到 user_config.databases
  → 构建下拉选项：[{label: "default", value: "default"}, {label: "HostB_SSD", value: "HostB_SSD"}, ...]
  → 当前选中 = localStorage.lastDatabase || "default"

@change:
  → 更新组件本地选中值
  → 不调 API。不写 localStorage。不改后端文件。

暴露:
  selectedDatabase: Ref<string>  （供父组件读取，作为请求参数）
  options: 下拉选项列表
```

### 模板
```html
<el-select v-model="selectedDatabase" placeholder="选择 database">
  <el-option v-for="opt in options" :key="opt.value" :label="opt.label" :value="opt.value" />
</el-select>
```

### 可选增强
- 切换时检查 `localStorage["modmanager:decisions:" + newValue]` 是否存在
  - 存在 → 下拉旁显示"有历史决策"
  - 不存在 → 无提示

---

## Task 3.4: `pages/DataSourcePage.vue`

### 删除
- `forestStore.storedDatabase = savedDb` 等跨 store 裸写（第 457-460 行）
- `forestStore.pipelineForm.databasePath = ''` 
- `forestStore.pipelineForm.manualSteamPath = ...`
- `forestStore.dbManualOverride = false`

### 新增
- 引入 `<DatabaseSelector />`，放在扫描按钮上方
- `scan()` 时用 `databaseSelector.selectedDatabase` 作为 `database_name` 参数
- `doSave()` 后写 `localStorage.lastDatabase = selectedDatabase`

### 修改
- `doSave()` 中删除 `output_path` 参数。只用 `database_name`

---

## Task 3.5: `pages/ForestPage.vue`

### 修改
- 引入 `<DatabaseSelector />`
- `prepareParams()` 改为：
  ```ts
  {
    database_name: databaseSelector.selectedDatabase,
    kmm_rule_paths: rules,
    managed_entries: localStorage.get("decisions:" + selectedDatabase)?.managed_entries,
    branch_decisions: localStorage.get("decisions:" + selectedDatabase)?.branch_decisions,
  }
  ```
- 不再依赖 `forestStore.storedDatabase`

### 删除
- 所有直接操作 `forestStore.pipelineForm.databasePath` 的代码
- `discoverDatabase()` 中不再设 `pipelineForm.manualSteamPath`

---

## Task 3.6: `pages/ComputePrepPage.vue`

### 新增
- 引入 `<DatabaseSelector />`
- 页面加载时若 `localStorage["decisions:" + selectedDatabase]` 存在 → 恢复上次 checkbox 状态

### 修改
- `POST /api/pipeline/compute` 请求体：
  ```json
  {
    "database_name": "...",
    "aggregated_rule_path": "...",
    "managed_entries": {...},   // 从 localStorage 或 checkbox 状态构造
    "branch_decisions": {...}   // 从 localStorage 读取
  }
  ```
- compute 成功后：写 `localStorage["results:" + database_name] = { trees_count, mapping_count, ... }`
- compute 成功后：写 `localStorage["decisions:" + database_name] = { managed_entries, branch_decisions }`
- 写 `localStorage.lastDatabase = selectedDatabase`

---

## Task 3.7: `pages/OperationsPage.vue`

### 删除
- 所有对 `wsInputs.database_path` 的引用
- 从 workspace 读状态的逻辑

### 修改
- 引入 `<DatabaseSelector />`（可选——此页面主要做备份/恢复/应用，不常换 database）
- backup/apply 请求体中加 `database_name`
- 摘要从 localStorage 读：`localStorage["results:" + selectedDatabase]`

---

## Task 3.8: `pages/AdvancedPage.vue`

### 修改
- Database tab 的"刷新"按钮：调 `POST /api/database/read { database_name }` 而非旧的 `/load { path }`
- Database tab 的"保存"按钮：调 `POST /api/database/save { database, database_name }` 不传 `output_path`
- 删除 Workspace tab（workspace 不存在了）或改为展示 localStorage 内容

### 新增
- 引入 `<DatabaseSelector />`

---

## Task 3.9: `pages/SettingsPage.vue`

### 修改
- `database_output_path` 输入框 → 删除
- 新增 `databases` 对象编辑器：可编辑 key-value 表（key = database name, value = path）
  - 复用已有的 el-table 行内编辑模式（DESIGN_GUI.md §四）
  - `default` 行可删除（删除后列表为空时显示"恢复默认"按钮）
  - 添加新行：尾部输入框填 name → 自动生成空 path
- 保存时：`POST /api/config/save { config }` 不传 `output_path`

### 删除
- 任何 workspace 相关 UI

---

## Task 3.10: `App.vue`

### 删除
- `onMounted` 中调 `POST /api/workspace/status` 的逻辑
- "无 user_config_path 则跳转 /settings" 的判断（user_config_path 不再由前端管理）

### 修改
- `onMounted` 可简化为空，或只做最基础的 health check

---

## Task 3.11: `utils/persistence.ts`

### 修改
- localStorage key 前缀确认：`modmanager:`
- 确认或新增以下 key 的读写方法（如果 persistence.ts 只做泛型 save/load，则只更新注释）：
  - `lastDatabase`
  - `decisions:{name}`
  - `results:{name}`

### 注释更新
说明职责边界：仅 UI 状态 + decisions/results 摘要。不存 database 扫描结果。

---

## 执行顺序

1. Task 3.0 — 清理（mock handlers + types）
2. Task 3.11 — persistence.ts（基础设施）
3. Task 3.3 — DatabaseSelector 组件（公共组件，最先写）
4. Task 3.1 — datasource store
5. Task 3.2 — forest store
6. Task 3.4 — DataSourcePage
7. Task 3.5 — ForestPage
8. Task 3.6 — ComputePrepPage
9. Task 3.7 — OperationsPage
10. Task 3.8 — AdvancedPage
11. Task 3.9 — SettingsPage
12. Task 3.10 — App.vue

---

## 验收

```bash
cd frontend && npm run build    # 构建成功
cd frontend && npm run test     # Vitest 全部通过（如需要更新测试）
```

# DESIGN_DATA_CLEANUP — 前端 localStorage 清退与数据流规范

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义前端 localStorage 中业务数据的清退清单、persistence.ts 新职责边界、以及清退后的前后端数据流规范。作为 Phase 2 前端改造的唯一执行依据。
> 创建：2026-05-13
> 更新：2026-05-14 — 清退后的 decisions/results 存前端 localStorage，非后端 workspace
> 更新：2026-05-14 — 【§十二补充裁定】分散 key 聚合为单一 `modmanager:workspace` key
> 依赖：DESIGN_GUI_WORKSPACE.md（前端 workspace 结构）

---

## 一、清退清单

### 1.1 需删除的 localStorage key

当前代码向 localStorage 写入以下 key（均带 `modmanager:` 前缀）：

| key | 内容 | 写入者 | 处置 |
|-----|------|--------|------|
| `datasource` | 完整 DataSourceState（扫描结果 + 表单输入） | `stores/datasource.ts` → `saveToCache()` | **删除 key 及读写代码** |
| `datasource-db` | 数据库副本（libraries, games, mods, warnings, errors, lastResult） | `stores/datasource.ts` → `_populateFromDatabase()` | **删除 key 及读写代码** |
| `forest-store` | Forest 页面数据（storedDatabase, pipelineForm, dbManualOverride, databaseSummary, userConfig） | `stores/forest.ts` → `watch` 自动持久化 | **删除 key 及读写代码** |

### 1.2 需删除/修改的代码

#### `stores/datasource.ts`

| 删除项 | 行 | 替代方案 |
|--------|-----|---------|
| `saveToCache()` | 172-191 | 表单输入（discoveryMode, manualPath）改为走 persistence.ts UI 状态存储 |
| `loadFromCache()` | 152-170 | 同上 |
| `clearCache()` | 193-196 | persistence.ts 提供 clear |
| `_populateFromDatabase()` 中的 `pers.save('datasource-db', ...)` | 324-334 | 扫描结果不缓存；每次进入页面重新调用后端 |
| store 初始化时的 `pers.load('datasource-db')` | 39-56 | 删掉，页面 mount 时调后端 |
| `const DS_KEY = 'datasource'` | 14 | 删掉 |
| 所有 `saveToCache()` 调用点 | — | 改为 walk through `persistence.ts`（仅 UI 状态）|

#### `stores/forest.ts`

| 删除项 | 行 | 替代方案 |
|--------|-----|---------|
| `savePersistentState()` | 286-293 | 后端 workspace |
| `loadPersistentState()` | 296-311 | 调 localStorage 读取 decisions/results |
| `watch(..., savePersistentState)` | 317-321 | 删除该 watch；业务状态通过 localStorage（decisions/results）管理，UI 状态通过 persistence.ts |
| `const PERSIST_KEY = 'forest-store'` | 38 | 删掉 |
| `loadPersistentState()` 调用 | 314 | 改为从 localStorage 读取 decisions/results |

#### `__tests__/`

| 测试文件 | 改动 |
|---------|------|
| `stores/datasource.test.ts` | 删除 `saveToCache` / `loadFromCache` / `clearCache` 测试；删除 `localStorage.getItem('modmanager:datasource')` 断言 |
| `utils/persistence.test.ts` | 保留——persistence.ts 本身仍存在，仅职责缩减 |
| `pages/DataSourcePage.test.ts` | 删除涉及 localStorage 数据恢复的测试逻辑 |
| `stores/forest.test.ts` | 删除涉及 `savePersistentState` / `loadPersistentState` 的测试 |

---

## 二、persistence.ts 新职责

### 2.1 定位

`persistence.ts` 仅负责 **无后端的纯 UI 状态** 持久化。任何需要后端参与才能产生的数据，均由后端 workspace 管理。

### 2.2 允许存储的内容

| 内容 | 类型 | 说明 |
|------|------|------|
| 当前 tab 位置 | `string` | `/settings`, `/forest`, `/operations`... |
| Sidebar 折叠状态 | `boolean` | `true` = 折叠，`false` = 展开 |
| DataSourcePage 表单输入 | 见下方 | discoveryMode, manualPath, workingPathstyle, greedyParsing |
| 库可见性开关 | `Record<number, boolean>` | `libraryVisibility` |
| 游戏可见性开关 | `Record<number, boolean>` | `gameVisibility` |
| `modmanager:workspace` | `object` | 聚合 workspace 对象（含 lastDatabase、perDatabase、aggregatedRuleSet、aggregatedRuleHash） |

workspace 结构见 `DESIGN_GUI_WORKSPACE.md` §二。

### 2.3 禁止存储的内容

- ❌ 数据库扫描结果（libraries, games, mods）
- ❌ pipeline 计算结果（trees, final_mapping, mapping_result）
- ❌ 警告/错误列表（warnings, errors）
- ❌ user_config 内容（从后端 `/api/config/discover` 获取）
- ❌ storedDatabase / databaseSummary / lastResult
- ❌ pipelineForm 中的业务字段（rulesPaths, backupDir, userConfigPath 等——这些属于后端管理）

### 2.4 错误处理变更

```typescript
// 旧：静默失败
try { pers.save(key, value) } catch { /* 忽略 */ }

// 新：非阻塞提示
try { pers.save(key, value) } catch {
  notify.warning("偏好保存失败，下次启动可能丢失设置")
}
```

`notify` 使用已有的 `notify.ts` 模块（`ElMessage.warning`）。

### 2.5 实现文件

仅修改 `frontend/src/utils/persistence.ts`——顶部注释声明新职责边界，save/load 增加 notify 错误处理。

---

## 三、清退后的数据流规范

### 3.1 核心原则

> **后端是唯一权威数据源。前端 Pinia store 仅暂存本次页面会话的内存状态。用户决策和计算结果摘要存前端 localStorage，compute 时传入后端。**

### 3.2 页面启动流程

```
App.vue mount()
  ├── 1. 从 localStorage 读取 workspace（`modmanager:workspace`）→ 提取 lastDatabase、perDatabase
  ├── 2. Persistence.load('ui-state') → 恢复 tab / sidebar / visibility
  └── 3. 根据状态渲染初始页面
```

### 3.3 页面切换时的数据流动

```
DataSourcePage → 扫描
  ├── POST /api/database/generate  → 获取纯 database（无 managed）
  └── 前端数据库切换时检查 workspace.perDatabase[name]?.decisions → 提示恢复决策

RulesOverviewPage → 浏览
  └── POST /api/rules/scan → 获得规则列表

ForestPage → 计算
  ├── 从 workspace.perDatabase[name].decisions 读 decisions
  ├── 从 workspace.aggregatedRuleSet 读聚合规则 dict
  ├── POST /api/pipeline/compute { database_name, aggregated_rule_set, managed_entries, branch_decisions }
  │   └── orchestrator 内部获取 database
  └── 计算完成 → 前端写 workspace.perDatabase[name].results

ConflictsPage → 决策
  ├── 从 workspace.perDatabase[name].decisions.branch_decisions 读
  └── 用户确认 → 写 workspace.perDatabase[name].decisions.branch_decisions

OperationsPage → 执行
  ├── 从工作区目录读 mapping（`GET /api/workspace/{id}/forest/mapping`）
  └── 按钮 → POST /api/workspace/{id}/pipeline/backup | apply
```

### 3.4 刷新页面时的状态恢复

| 页面 | 恢复来源 |
|------|---------|
| DataSourcePage | `sessionStorage['modmanager:uiState:datasource']` 恢复可见性/表单；扫描结果通过 API 重新加载 |
| ForestPage | `GET /api/workspace/{id}/forest/mapping` 从工作区目录恢复完整 trees/mapping |
| ConflictsPage | `GET /api/workspace/{id}/decisions/load` 从工作区目录恢复 decisions |
| ComputePrepPage | `sessionStorage['modmanager:uiState:{id}']` 恢复可见性；`GET /api/workspace/{id}/rules/aggregated` 恢复规则集 |
| SettingsPage | `POST /api/config/discover` → user_config |
| RulesOverviewPage | `POST /api/config/discover` → user_config.rule_sources → `/api/rules/scan` |

---

## 四、不可回退边界

清退完成后，以下条件必须成立：

1. `localStorage` 和 `sessionStorage` 中**不存在** `modmanager:workspace`、`modmanager:lastDatabase`、`modmanager:decisions:*`、`modmanager:results:*`
2. `datasource.ts` 中 **不存在** `saveToCache`、`loadFromCache`、`clearCache` 方法
3. `forest.ts` 中 **不存在** `savePersistentState`、`loadPersistentState` 方法及 `watch` 自动持久化
4. 任何 pinia store 的 `ref` / `reactive` 初始化时不得从 localStorage 读取业务数据
5. 前端 Vitest 全部通过（清退后的测试覆盖新的数据流）

---

## 五、验收条件

| 验收项 | 条件 |
|-------|------|
| 静态检查 | `grep -r "datasource-db\|forest-store\|saveToCache\|loadFromCache\|savePersistentState\|loadPersistentState" frontend/src/` 返回空（不含注释） |
| 动态检查 | 启动应用 → 打开 DevTools → Application > Storage → Local Storage / Session Storage → 仅存在 `sidebarCollapsed`、`activeTab`、`currentWorkspaceId`、`uiState:*` 键，无业务数据 |
| 功能检查 | 在 DataSourcePage 扫描 → 进入工作区 → compute → 切换 ForestPage → 刷新页面 → ForestPage 从工作区目录恢复完整数据 |
| 测试 | `cd frontend && npm run test` 全部通过 |

---

## 六、决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | persistence.ts 是否保留 | 保留，职责缩减为仅 UI 状态 |
| D2 | decisions/results 归属 | decisions/results 存前端 localStorage（`modmanager:workspace`），非后端 workspace |
| D3 | 清退方式 | 一步到位，不保留过渡期双写 |
| D4 | 错误处理 | 静默 → notify.warning |

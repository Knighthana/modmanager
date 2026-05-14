# TODO-20: 选项卡解耦审查报告

> 状态: 审查完成
> 日期: 2026-05-13
> 审查范围: `forest.ts` + `datasource.ts` 跨页面读写

---

## 一、审查方法

逐字段检查以下存储中，每个字段的写入方和读取方：

| Store | 文件 |
|-------|------|
| `forest` | `frontend/src/stores/forest.ts` |
| `datasource` | `frontend/src/stores/datasource.ts` |

---

## 二、`forest.ts` 耦合分析

### 2.1 字段读写矩阵

| 字段 | 写入方 | 读取方 | 耦合等级 |
|------|--------|--------|:-------:|
| `trees` | ForestPage (`onCompute`/`onRun` via `runPipeline`/`computeOnly`) | ConflictsPage (via `conflictList`), OperationsPage, ForestViewer | ✅ 正常 |
| `finalMapping` | ForestPage | OperationsPage | ✅ 正常 |
| `branchDecisions` | ForestViewer (`setDecision`), `initFromWorkspace` | ConflictsPage, LayoutShell (badge), OperationsPage | ✅ 正常 |
| `errors` | ForestPage | ConflictsPage, OperationsPage | ✅ 正常 |
| `warnings` | ForestPage | OperationsPage | ✅ 正常 |
| `svgContent` | ForestPage (`fetchVisualization`) | ForestViewer | ✅ 正常 |
| `isRunning` | ForestPage | LayoutShell, ForestViewer, SseStatusBar | ✅ 正常 |
| `progress` | ForestPage | SseStatusBar | ✅ 正常 |
| `pipelineForm.*` | **DataSourcePage** (lines 420–431) | ForestPage, OperationsPage | 🔴 **耦合** |
| `storedDatabase` | **DataSourcePage** (line 419) | ForestPage | 🔴 **耦合** |
| `dbManualOverride` | **DataSourcePage** (line 422) | ForestPage (已简化不再依赖) | 🔴 **耦合** |
| `userConfig` | `forestStore.loadConfig()` 被 DataSourcePage 调用 | ForestPage | 🔴 **耦合** |
| `lastSuccessfulParams` | ForestPage | ConflictsPage | ✅ 正常 |

### 2.2 关键耦合点

#### 耦合点 #1: DataSourcePage 直接写入 `forestStore.pipelineForm`

**位置**: `frontend/src/pages/DataSourcePage.vue` 第 419–432 行

```typescript
// doSave() 内部:
forestStore.storedDatabase = savedDb                             // 直接写 forest store
forestStore.pipelineForm.manualSteamPath = store.manualPath      // 直接跨页写表单
forestStore.pipelineForm.databasePath = ''                        // 直接跨页写表单
forestStore.dbManualOverride = false                              // 直接写 forest store
// ...
if (!forestStore.userConfig) {
  await forestStore.loadConfig()                                  // 跨页调用 action
}
if (forestStore.userConfig) {
  forestStore.pipelineForm.userConfigPath = '/tmp/modmanager_userconfig_generated.json'  // 直接写表单
}
```

**问题**: DataSourcePage 直接修改 ForestStore 的内部字段，违反 "API 为唯一信使" 和 "禁止跨页面直接调用" 原则。

**建议**: 应通过后端 API 间接传递（例如 DataSourcePage 保存 database 后，ForestPage 从 API 重新加载），或通过 workspace API 统一状态管理。

#### 耦合点 #2: `forestStore` 同时做"数据持有"和"计算触发"

ForestStore 既持有 `storedDatabase` / `pipelineForm` 等输入数据，又负责触发计算 (`computeOnly` / `runPipeline`)。这导致输入来源混乱（DataSourcePage、SettingsPage、未来 RulesOverviewPage 都往里写）。

---

## 三、`datasource.ts` 耦合分析

### 3.1 字段读写矩阵

| 字段 | 写入方 | 读取方 | 耦合等级 |
|------|--------|--------|:-------:|
| `discoveryMode` | DataSourcePage | DataSourcePage | ✅ 自包含 |
| `manualPath` | DataSourcePage | DataSourcePage | ✅ 自包含 |
| `workingPathstyle` | DataSourcePage | DataSourcePage | ✅ 自包含 |
| `greedyParsing` | DataSourcePage | DataSourcePage | ✅ 自包含 |
| `databaseOutputPath` | DataSourcePage | DataSourcePage | ✅ 自包含 |
| `libraries` | DataSourcePage (scan) | DataSourcePage | ✅ 自包含 |
| `games` | DataSourcePage (scan) | DataSourcePage | ✅ 自包含 |
| `mods` | DataSourcePage (scan) | DataSourcePage | ✅ 自包含 |
| `warnings` | DataSourcePage (scan) | DataSourcePage | ✅ 自包含 |
| `errors` | DataSourcePage (scan) | DataSourcePage | ✅ 自包含 |
| `libraryVisibility` | DataSourcePage | DataSourcePage | ✅ 自包含 |
| `gameVisibility` | DataSourcePage | DataSourcePage | ✅ 自包含 |
| `duplicateResolutions` | DataSourcePage | DataSourcePage | ✅ 自包含 |
| `isScanning` | DataSourcePage | DataSourcePage | ✅ 自包含 |
| `lastResult` | DataSourcePage (scan) | DataSourcePage (`doSave`) | ✅ 自包含 |

**结论**: `datasource.ts` 无跨页面耦合。所有字段只在 DataSourcePage 内部读写。

---

## 四、其他跨页面依赖

| 源 | 目标 | 访问方式 | 耦合等级 |
|----|------|---------|:-------:|
| LayoutShell | `forestStore.isRunning` | 直接读 | ✅ 可接受（UI 状态） |
| LayoutShell | `forestStore.unresolvedCount` | 直接读 computed | ✅ 可接受（badge） |
| LayoutShell | `forestStore.progress` | 直接读 (via SseStatusBar) | ✅ 可接受 |
| ConflictsPage | `forestStore.conflictList` | 直接读 computed | ✅ 正常（同一 store 页面间共享） |
| ConflictsPage | `forestStore.branchDecisions` | 直接读写 | ✅ 正常 |
| ConflictsPage | `forestStore.lastSuccessfulParams` | 直接读 | ✅ 正常 |
| OperationsPage | `forestStore.trees/finalMapping/errors/warnings` | 直接读 | ✅ 正常 |
| OperationsPage | `forestStore.pipelineForm.backupDir` | 直接读 | ✅ 正常 |
| ForestViewer | `forestStore.svgContent/trees` | 直接读写 | ✅ 正常（组件内使用） |
| ForestViewer | `forestStore.setDecision()` | 调用 action | ✅ 正常 |

---

## 五、总结

### 5.1 需修复的耦合点（严重）

| # | 问题 | 文件 | 行号 |
|---|------|------|------|
| 1 | DataSourcePage 直接写入 `forestStore.storedDatabase` 和 `pipelineForm` 字段 | `DataSourcePage.vue` | 419–432 |

**建议修复方式**: DataSourcePage 保存 database 后，应通过 `POST /api/workspace/save-inputs` 将 database_path 写入 workspace；ForestPage 从 workspace API 加载输入数据，而非依赖跨 store 写入。

### 5.2 已标记的点

以下位置已添加 `// TODO-20: decouple` 注释标记：

- `DataSourcePage.vue:419` — `forestStore.storedDatabase = savedDb`

### 5.3 正常耦合（无需修复）

LayoutShell 读取 forestStore 的 `isRunning` / `unresolvedCount` / `progress` 属于 UI 状态共享，符合 Pinia 设计初衷。同一流程的页面（ForestPage / ConflictsPage / OperationsPage）之间通过 `forestStore` 共享计算结果链也属于合理使用。

---

## 六、附录：完整跨页面 store 访问清单

```
[DataSourcePage] ──直接写──→ [forestStore.storedDatabase]
[DataSourcePage] ──直接写──→ [forestStore.pipelineForm.*]
[DataSourcePage] ──直接写──→ [forestStore.dbManualOverride]
[DataSourcePage] ──调用──→  [forestStore.loadConfig()]

[LayoutShell]    ──直接读──→ [forestStore.isRunning]
[LayoutShell]    ──直接读──→ [forestStore.unresolvedCount]
[SseStatusBar]   ──直接读──→ [forestStore.progress]

[ForestViewer]   ──直接读──→ [forestStore.svgContent]
[ForestViewer]   ──调用──→  [forestStore.setDecision()]

[ConflictsPage]  ──直接读──→ [forestStore.conflictList]
[ConflictsPage]  ──直接读──→ [forestStore.branchDecisions]
[ConflictsPage]  ──直接读──→ [forestStore.lastSuccessfulParams]

[OperationsPage] ──直接读──→ [forestStore.trees]
[OperationsPage] ──直接读──→ [forestStore.finalMapping]
[OperationsPage] ──直接读──→ [forestStore.errors/warnings]
[OperationsPage] ──直接读──→ [forestStore.pipelineForm.backupDir]
```

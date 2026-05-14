# REFACTOR — database_path 流转简化与 workspace 职责清理

> Status: plan
> Authority: arch
> Created: 2026-05-14
> Scope: 前端 ↔ 后端 database 数据流转、workspace.json 结构、API 端点语义
> Affected: user_config.json / workspace.json / API / 前端 Pinia stores / DataSourcePage / ForestPage / OperationsPage / AdvancedPage

---

## 一、核心原则（本次修正的基石）

1. **`user_config.json` 是文件路径的唯一权威来源。** 后端自己知道所有文件在哪，前端不需要知道任何路径。
2. **前端只告诉后端"做什么"，不告诉后端"在哪做"。** database 的读取、保存、扫描，前端一律不传路径。
3. **workspace 只存储用户主观选择 + 计算结果摘要。** 不存储任何文件路径（那是 user_config 的事），不存储"要干什么"（那是 aggregated_rule 的事）。
4. **高级用户可通过名称引用自定义 database，无需知道路径。**

---

## 二、user_config.json 扩展

### 2.1 新增字段

```json
{
  "database_output_path": "~/.local/share/kmm/database.json",
  "custom_databases": [
    { "name": "wsl_scan", "path": "/mnt/d/database_wsl.json" },
    { "name": "backup_variant", "path": "/tmp/database_v2.json" }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `database_output_path` | `string` | **默认 database 路径**（已有，保留） |
| `custom_databases` | `object[]` | **自定义 database 名称→路径映射**（新增）。仅在高级用户需要非默认 database 时使用 |
| `custom_databases[].name` | `string` | 自定义 database 的名称标识 |
| `custom_databases[].path` | `string` | 该 database 的文件路径 |

### 2.2 database 解析规则（后端内部）

```
前端传入 database_ref:
  ├── null / 未传 / 空字符串 → 使用默认：user_config.database_output_path
  ├── "wsl_scan"（名称）       → 查 user_config.custom_databases，按 name 匹配
  └── 查不到                    → 返回错误 "E_UNKNOWN_DATABASE: 未知的 database 名称 'xxx'"
```

**前端除了 SettingsPage 之外，永远不需要接触路径。** 其他所有页面只需要知道名称（或者默认啥也不传）。

---

## 三、workspace.json 精简

### 3.1 当前结构（需要删除的部分以 ~~删除线~~ 标记）

```json
{
  "session_updated": "...",
  "inputs": {                              // ← 整个块删除
    "database_path": "...",                // → user_config.database_output_path
    "rule_paths": ["..."],                 // → user_config.rule_sources
    "aggregated_rule_path": "...",         // → user_config.aggregated_ruleset_output_path
    "user_config_path": "...",             // → 后端平台默认路径
    "discovery_mode": "auto",              // → 前端 localStorage（UI 状态）
    "discovery_manual_paths": []           // → 前端 localStorage（UI 状态）
  },
  "decisions": {
    "branch_decisions": {}
    // ↓ 新增
    // "managed_entries": { "game": {...}, "mod": {...} }
  },
  "results": {
    "last_compute": { ... }
  }
}
```

### 3.2 目标结构

```json
{
  "session_updated": "2026-05-14T...Z",
  "decisions": {
    "branch_decisions": {
      "/path/to/tree/root/a": "/path/to/source/m1"
    },
    "managed_entries": {
      "game": { "270150": ["/mnt/d/.../RWR"] },
      "mod": { "270150:2606099273": ["/mnt/d/.../mod"] }
    }
  },
  "results": {
    "last_compute": {
      "trees_count": 42,
      "mapping_count": 15,
      "warnings": [],
      "errors": [],
      "stats": {},
      "inputs_hash": "abc123",
      "timestamp": "2026-05-14T..."
    }
  }
}
```

### 3.3 职责说明

| 字段 | 职责 | 为什么在这 |
|------|------|-----------|
| `decisions.branch_decisions` | 用户对冲突分支的选择 | 用户主观决策，需跨刷新持久化 |
| `decisions.managed_entries` | 用户对重复条目的取舍 | 同上，与 branch_decisions 语义同构 |
| `results.last_compute` | 上次计算摘要 | 供 UI 展示"上次结果"，不存完整数据 |
| ~~`inputs.*`~~ | ~~文件路径 / 扫描参数~~ | **删除。** 路径 → user_config；UI 状态 → localStorage |

### 3.4 关于 managed_entries 归属的说明

`managed_entries` 当前作为 compute 的可选参数传递，但存在两个问题：
1. 与 `branch_decisions` 处理不一致（后者有 workspace API 读写）
2. 页面刷新后丢失

`managed_entries` 与 `branch_decisions` 的语义同构：
- `managed_entries`："磁盘上有两份 appid=270150，我认 /mnt/d/.../RWR 这份"
- `branch_decisions`："树上有两条分支，我走 /path/to/source/m1 这条"

两者都满足"用户主观选择、需跨刷新持久化、属于当前工作会话"的定义。**统一放入 `workspace.decisions`。**

---

## 四、API 端点修正

### 4.1 `POST /api/database/generate` — 扫描

**修正前：**
```json
{ "mode": "auto", "paths": null, "working_pathstyle": "linux",
  "greedy_parsing": false, "cache_path": "/tmp/..." }
```

**修正后：**
```json
{ "mode": "auto", "paths": null, "working_pathstyle": "linux",
  "greedy_parsing": false, "database_ref": null }
```

| 变更 | 说明 |
|------|------|
| 删除 `cache_path` | 后端自行根据 user_config 管理缓存策略 |
| 新增 `database_ref`（可选） | 高级用户指定非默认 database 的名称。`null` = 用默认 |

**后端行为：**
1. 解析 `database_ref` → 确定目标 database 路径（默认或自定义）
2. 按 mode 执行扫描
3. 将结果写入该 database 路径
4. 返回完整 database dict

### 4.2 `POST /api/database/current` — 获取当前 database（新端点 / 改造 load）

**修正前（`/database/load`）：**
```json
{ "path": "/some/path/database.json" }
```

**修正后（改为 `/database/current`）：**
```json
{ "database_ref": null }
```

| 变更 | 说明 |
|------|------|
| 删除 `path` 参数 | 前端不应知道路径 |
| 新增 `database_ref`（可选） | `null` = 默认 database |
| 改名 `load` → `current` | 语义更明确："给我当前生效的 database" |

**后端行为：**
1. 解析 `database_ref` → 确定路径（默认或自定义）
2. 读取并返回 database dict + 文件元信息（path, size, mtime）

### 4.3 `POST /api/database/save` — 保存

**修正前：**
```json
{ "database": {...}, "output_path": "/tmp/..." }
```

**修正后：**
```json
{ "database": {...}, "database_ref": null }
```

| 变更 | 说明 |
|------|------|
| 删除 `output_path` | 后端从 user_config 确定路径 |
| 新增 `database_ref`（可选） | `null` = 默认 database |

### 4.4 `POST /api/pipeline/compute` 和 `/api/pipeline/run`

**修正前（database 字段是 `Any`——path 字符串或 dict）：**
```json
{ "database": "/path/to/db.json" | {...dict...}, "kmm_rule_paths": [...],
  "user_config_path": "...", "aggregated_rule_path": "...", ... }
```

**修正后：**
```json
{ "database_ref": null, "kmm_rule_paths": [...],
  "aggregated_rule_path": "...", ... }
```

| 变更 | 说明 |
|------|------|
| `database` → `database_ref` | 统一为引用名称（`null` = 默认） |
| 删除 `user_config_path` | 后端内部从 user_config 获取一切 |
| `database_ref` 语义 | `null`=默认 database；`"name"`=custom_databases 中定义的 |
| 后端行为 | 自行从 user_config 解析路径 → 加载 dict → 传入 orchestrator |

### 4.5 `POST /api/pipeline/backup` 和 `/api/pipeline/apply`

**修正前（database 字段用于推导 backup_dir）：**
```json
{ "database": null | {...dict...}, "user_config_path": null | "...", ... }
```

**修正后：**
```json
{ "database_ref": null, ... }
```

后端内部自行从 user_config 获取 database 路径和 user_config 内容来推导 backup_dir。

### 4.6 `POST /api/rules/aggregate`

**修正前：**
```python
output_path = workspace.get("inputs", {}).get("aggregated_rule_path", "")
```

**修正后：**
```python
output_path = user_config.get("aggregated_ruleset_output_path")
# 若 user_config 未定义，使用平台默认路径
```

不从 workspace 读取路径。

### 4.7 `POST /api/rules/affected-entries`

**修正前：**
```python
db_path = workspace.get("inputs", {}).get("database_path", "")
```
**修正后：**
```python
db_path = user_config.get("database_output_path")
# 或通过 database_ref 参数指定（与 generate 一致）
```

### 4.8 `POST /api/workspace/save-inputs` — 删除

整个端点及其对应的 `SaveInputsRequest` schema 删除。`inputs` 块不再存在。

### 4.9 `POST /api/workspace/save-decisions` — 扩展

```json
{
  "branch_decisions": { ... },
  "managed_entries": { "game": {...}, "mod": {...} }
}
```

两个字段均可选，仅传入需要更新的。

### 4.10 `GET /api/workspace/status` — 返回结构变更

不再包含 `inputs` 块。保留 `decisions`（含 `managed_entries`）和 `results`。

### 4.11 `POST /api/config/save` — 路径修正

**修正前：**
```json
{ "config": {...}, "output_path": "/tmp/modmanager_userconfig_generated.json" }
```

**修正后：**
```json
{ "config": {...} }
```

后端自行确定 user_config 的默认保存路径。

---

## 五、前端修正

### 5.1 `datasourceStore` — 删除 `databaseOutputPath`

- 删除 `databaseOutputPath` 状态字段
- `scan()` 不再传 `cache_path` 参数
- `scan()` 增加 `database_ref` 参数（可选，默认 null）

### 5.2 `forestStore` — 删除 `pipelineForm.databasePath` 和 `databaseJson`

- 删除 `pipelineForm.databasePath`（string）—— 后端不需要
- 删除 `pipelineForm.databaseJson`（死代码）—— 本来就没用
- 新增 `pipelineForm.databaseRef`（string | null）—— 仅名称，不存路径
- 删除 `pipelineForm.userConfigPath` —— 后端自己知道
- ~~删除 workspace `save-inputs` 的 watcher~~ —— inputs 块不存了
- `storedDatabase` 保留（内存态 dict，跨页面传递）
- `initFromWorkspace()` 简化为仅恢复 `branch_decisions` + `managed_entries`

### 5.3 `DataSourcePage` — 简化

- `doSave()` 中删除 `forestStore.pipelineForm.databasePath = ''` 这类跨 store 裸写
- `doSave()` 调用 `/database/save` 时只传 `{ database }`，不传 `output_path`
- 与 forestStore 之间的数据传递改用明确的 action（而非直接赋值字段）

### 5.4 `ForestPage` — 简化

- `prepareParams()` 改为传 `database_ref` 而非 `database` dict
  - 或者：若 `storedDatabase` 有值（DataSourcePage 刚传过来的内存 dict），仍可直接传 dict（优化：避免后端重复读文件）
  - 若 `storedDatabase` 为空（刷新后），后端自行从 user_config 加载

### 5.5 `OperationsPage` — 简化

- 不再从 workspace 读 `database_path` 字符串传给 backup 端点
- 直接传 `database_ref: null`，后端自己搞定

### 5.6 `AdvancedPage` — 简化

- "刷新"按钮调用 `POST /api/database/current`（无参数），不再传 `path`
- "保存"按钮调用 `POST /api/database/save`（无 `output_path`）

### 5.7 `SettingsPage` — 新增 custom_databases 管理

- 新增一个列表表单，管理 `custom_databases` 的 name/path 对
- 这是**唯一**接触 database 路径的前端页面

### 5.8 localStorage 调整

- `DataSourcePage` 的持久化 key 中删除 `databaseOutputPath`（该字段不再存在）
- 保留 `discoveryMode`、`manualPaths`、`workingPathstyle`、`greedyParsing`、`libraryVisibility`、`gameVisibility`

### 5.9 `App.vue` — 启动恢复

- 启动时调用 `GET /api/workspace/status`
- 恢复 `forestStore.branchDecisions` 和 `forestStore.managedEntries`（不再恢复 inputs）

---

## 六、后端修正

### 6.1 `bootstrap.py`

- `discover_user_config()` 从三级搜索合并改为单级搜索（对齐 DESIGN_STORAGE.md §3.1-3.2）
- 新增 `first_use` 机制：文件不存在时自动创建空配置
- `generate_database()`：`cache_path` 参数保留（内部优化），但调用方不再从前端传入

### 6.2 `workspace.py`

- `DEFAULT_WORKSPACE` 删除 `inputs` 块
- `DEFAULT_WORKSPACE.decisions` 新增 `managed_entries: {}`
- 删除 `SaveInputsRequest` schema（`schemas.py`）
- `merge_workspace` 的 `section` 参数枚举从 `{"inputs","decisions","results"}` 变为 `{"decisions","results"}`

### 6.3 `schemas.py`

- 删除 `SaveInputsRequest`
- `LoadDatabaseRequest` → 改为 `CurrentDatabaseRequest`（`database_ref: str | None = None`）
- `SaveDatabaseRequest.output_path` → 改为 `database_ref: str | None = None`
- `GenerateDatabaseRequest.cache_path` → 删除；新增 `database_ref: str | None = None`
- `ComputeRequest` / `RunRequest`：`database: Any` → `database_ref: str | None = None`
- `BackupRequest` / `ApplyRequest`：`database` + `user_config_path` → `database_ref: str | None = None`
- `SaveConfigRequest.output_path` → 删除
- `SaveDecisionsRequest`：新增 `managed_entries: dict | None = None`

### 6.4 `routes/database.py`

- 新增 `resolve_database_path(ref: str | None, user_config: dict) -> str` 工具函数
- `/generate`：接受 `database_ref`，删除 `cache_path` 参数
- `/load` → 改为 `/current`：接受 `database_ref`
- `/save`：接受 `database_ref`

### 6.5 `routes/pipeline.py`

- `/compute` / `/run`：`database` 字段改为 `database_ref`。后端解析路径 → 加载 dict → 传入 orchestrator
- `/backup` / `/apply`：不再接收 `user_config_path`。内部自己读 user_config。

### 6.6 `routes/rules.py`

- `/aggregate`：不再从 workspace 读 `aggregated_rule_path`，改为从 user_config 读
- `/affected-entries`：不再从 workspace 读 `database_path`，改为从 user_config 读

### 6.7 `routes/workspace.py`

- 删除 `workspace_save_inputs` 端点和路由
- `workspace_save_decisions`：扩展为同时接受 `managed_entries`

---

## 七、受影响文件清单

### 修改

| 文件 | 变更类型 |
|------|----------|
| `repo_spec/user_config.schema.json` | 新增 `custom_databases` 字段 |
| `src/modmanager/workspace.py` | 删除 `inputs` 块，新增 `managed_entries` |
| `src/modmanager/bootstrap.py` | user_config 单级搜索 + first_use 机制 |
| `src/modmanager_web/schemas.py` | 多个 request schema 修改（见 §六.3） |
| `src/modmanager_web/routes/database.py` | 端点语义变更 |
| `src/modmanager_web/routes/pipeline.py` | database_ref 替代 database + user_config_path |
| `src/modmanager_web/routes/rules.py` | 不再从 workspace 读路径 |
| `src/modmanager_web/routes/workspace.py` | 删除 save-inputs，扩展 save-decisions |
| `frontend/src/stores/datasource.ts` | 删除 databaseOutputPath |
| `frontend/src/stores/forest.ts` | 删除 pipelineForm.databasePath，新增 databaseRef |
| `frontend/src/pages/DataSourcePage.vue` | 简化 save/scan 流程 |
| `frontend/src/pages/ForestPage.vue` | 简化 prepareParams |
| `frontend/src/pages/OperationsPage.vue` | 简化为传 database_ref |
| `frontend/src/pages/AdvancedPage.vue` | 使用 /database/current |
| `frontend/src/pages/SettingsPage.vue` | 新增 custom_databases 管理 UI |
| `frontend/src/App.vue` | 简化 initFromWorkspace |

### 新增

| 文件 | 说明 |
|------|------|
| （无需新增文件） | — |

### 删除

| 文件/内容 | 说明 |
|------|------|
| `forestStore.pipelineForm.databaseJson` | 死代码 |
| `forestStore.pipelineForm.userConfigPath` | 后端自己知道 |
| `workspace.inputs` 整块 | 路径归 user_config，UI 状态归 localStorage |
| `POST /api/workspace/save-inputs` 端点 | 不再需要 |
| `SaveInputsRequest` schema | 不再需要 |

---

## 八、十二个绕圈模式的解决

| # | 问题 | 解决方案 |
|---|------|---------|
| 1 | database_path 双存（user_config + workspace） | 仅存 user_config |
| 2 | /database/load 需要前端传 path | 改为 /database/current，无 path 参数 |
| 3 | /database/save 需要前端传 output_path | 删除 output_path 参数 |
| 4 | database 参数是 `Any`，行为不一致 | 统一为 `database_ref` |
| 5 | OperationsPage 把 path 字符串当 database 传 | 改为传 `database_ref: null` |
| 6 | pipelineForm.databasePath 是多余中间人 | 删除 |
| 7 | datasourceStore.databaseOutputPath 与 user_config 不同步 | 删除，统一由 user_config 管理 |
| 8 | loadConfig 写到 /tmp/ | 删除 output_path，后端写入默认位置 |
| 9 | discoverDatabase 扫描不落地 | 后端扫描后直接写入 database 路径 |
| 10 | DataSourcePage 跨 store 裸写 | 改用明确的 store action |
| 11 | databaseJson 死代码 | 删除 |
| 12 | cache_path 前传后 | 删除该参数 |

---

## 九、实施顺序建议

1. **Phase 1** — user_config 扩展（schema + 代码）
2. **Phase 2** — workspace 精简（删除 inputs，managed_entries 迁移）
3. **Phase 3** — API 端点语义修正（database 相关端点）
4. **Phase 4** — pipeline / rules / backup 端点修正（database_ref 替代）
5. **Phase 5** — 前端 Pinia store 修正
6. **Phase 6** — 前端页面修正
7. **Phase 7** — 文档同步更新（设计文档 + REST API 文档）

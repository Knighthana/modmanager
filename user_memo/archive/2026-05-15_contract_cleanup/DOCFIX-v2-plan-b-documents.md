# DOCFIX-v2 — 方案 B 文档修正清单

> Status: plan
> Authority: arch
> Created: 2026-05-14
> Source: `work_memo/2026-05-14_decisions.md`（vFinal 方案 B）
> 原则：workspace.json 不存在于后端。用户决策存前端 localStorage。一个概念一份定义，其余 extern 引用。

---

## 最大改动：DESIGN_WORKSPACE_STATE.md → DESIGN_GUI_WORKSPACE.md

### 操作
1. 将 `DESIGN_WORKSPACE_STATE.md` 复制到 `archive/DESIGN_WORKSPACE_STATE_2026-05-14.md`
2. 原位重命名为 `DESIGN_GUI_WORKSPACE.md`
3. 重写内容

### 新内容
- **标题**：`# DESIGN_GUI_WORKSPACE — 前端用户决策与结果存储`
- **定位**：workspace 逻辑迁移到前端。不再有后端 workspace.json 文件或 REST API。decisions 和 results 存 localStorage。
- **存储结构**：

  ```
  modmanager:lastDatabase          ← "HOSTB_SSD"  
  modmanager:decisions:default     ← { managed_entries: {...}, branch_decisions: {...} }
  modmanager:decisions:HOSTB_SSD   ← { managed_entries: {...}, branch_decisions: {...} }
  modmanager:results:default       ← { trees_count, mapping_count, warnings, errors, stats, timestamp }
  modmanager:results:HOSTB_SSD     ← { trees_count, mapping_count, ... }
  ```

- **decisions 格式**（保留原文档定义）：
  - `managed_entries`：`{ game: {appid: [path]}, mod: {mixed_id: [path]} }`
  - `branch_decisions`：`{ root_path: chosen_source_path }`
- **results 格式**：`{ trees_count, mapping_count, warnings, errors, stats, inputs_hash, timestamp }`
- **DatabaseSelector 组件行为**：
  - 下拉选中值 = 组件本地状态。不改 localStorage。不改后端文件。
  - 用户点操作按钮时，选中值作为 `database_name?` 参数传入请求
  - 下拉切换时检查 `decisions:{新name}` 是否存在 → 提示"恢复上次决策"或"无历史决策"
  - 刷新恢复：读 `lastDatabase` 恢复选中
- **compute 时**：前端从 localStorage 读 `decisions:{name}` → 放进 `POST /api/pipeline/compute` 请求体
- **compute 后**：前端从响应中提取摘要 → 写 `results:{name}`
- **SettingsPage 改名/删除 database**：前端同步清理/迁移对应 localStorage key
- **不再包含**：REST API 端点、save-* 方法、merge_workspace、后端文件路径描述
- **元数据**：Status: active / Authority: authoritative / Read-Tier: task-scoped / 更新：2026-05-14

---

## 其余文档修改

### 1. `DESIGN_STORAGE.md`

| 位置 | 改什么 |
|------|--------|
| §3.5 字段表 | `database_output_path` → 删除。新增 `databases` 对象：`{ [name: string]: { path: string } }`。说明对象天然防重、每个 entry 是对象为未来扩展留空间 |
| §4 database.json | 路径来源改为 `user_config.databases[name].path`。`name` 由前端请求参数 `database_name?` 指定，不传则用默认（databases 对象的第一个 key） |
| §5 workspace | 整节改为：`## 5. 用户决策与结果 —— 前端 localStorage`。说明：workspace.json 已撤销。decisions 和 results 存前端 localStorage，compute 时作为参数传入后端。格式见 `DESIGN_GUI_WORKSPACE.md`。 |
| §8.3 允许存储表 | 加 `decisions:{name}`、`results:{name}`、`lastDatabase` |
| §10 决策记录 | D8 更新为"decisions/results 存前端 localStorage"；D2（若存在）更新为"workspace 文件已撤销" |

### 2. `DESIGN_REST_API.md`

| 位置 | 改什么 |
|------|--------|
| 端点表（§4 开头附近） | 删除全部 workspace 行：`GET /api/workspace/status`、`POST /api/workspace/save-inputs`、`POST /api/workspace/save-decisions`、`POST /api/workspace/save-results` |
| `POST /api/database/generate` | 请求体：`{ mode, paths?, working_pathstyle, greedy_parsing, database_name? }`。说明：database_name 不传则用 user_config.databases 第一个 key |
| `POST /api/database/read`（原 load） | 改名 `read`。请求体：`{ database_name? }`。说明：后端查 user_config.databases[name].path → 加载 → 返回 |
| `POST /api/database/save` | 请求体：`{ database, database_name? }`。删除 `output_path` |
| `POST /api/pipeline/compute` | 请求体：`{ database_name?, aggregated_rule_path?, kmm_rule_paths?, managed_entries?, branch_decisions?, action_orders? }`。说明：database 由 orchestrator 内部从 user_config 加载；managed_entries 和 branch_decisions 由调用方传入 |
| `POST /api/pipeline/run` | 同上 + `{ backup_dir?, dry_run }` |
| `POST /api/pipeline/backup` | 请求体：`{ mapping_result, backup_dir? }`。删除 `database`、`user_config_path` |
| `POST /api/pipeline/apply` | 同上 |
| `POST /api/config/save` | 删除 `output_path` 参数 |
| §6 Pydantic Schema | 删除 `SaveInputsRequest`、`SaveDecisionsRequest`、`SaveResultsRequest`。`GenerateDatabaseRequest` 删 `cache_path`。`SaveDatabaseRequest` 删 `output_path`。`ComputeRequest` 删 `database: Any`、`user_config_path`；加 `database_name?: str`、`managed_entries?: dict`、`branch_decisions?: dict`。`RunRequest` 同上。`BackupRequest` / `ApplyRequest` 删 `database`、`user_config_path` |

### 3. `DESIGN_GUI.md`

| 位置 | 改什么 |
|------|--------|
| §3.1 DataSourcePage 关键约束 | 加"database 下拉组件：用户选择要操作的目标 database。选项来自 user_config.databases" |
| §3.3 计算准备 | 加"下拉组件同上" |
| §3.7 高级 | Database tab 数据来源改为 `POST /api/database/read` |
| §六 数据流规范 | 删除 `POST /api/workspace/*` 全部行。加上：`POST /api/pipeline/compute → 接受 managed_entries? + branch_decisions? 参数`。加上 DatabaseSelector 组件描述 |
| §九 决策记录 | D2 更新为"managed 归属：前端 localStorage，compute 时作为参数传入" |

### 4. `DESIGN_COMPUTE_PREP_PAGE.md`

| 位置 | 改什么 |
|------|--------|
| §五.1 请求 | 请求体改为：`POST /api/pipeline/compute { database_name?, aggregated_rule_path, managed_entries?, branch_decisions? }` |
| §五.2 响应处理 | 删除 `POST /api/workspace/save-results`。改为："成功后前端写 `results:{name}` 到 localStorage" |
| §六 数据流 | 删除 `GET /api/workspace/status` 行和 `save-inputs` 行。改为从前端 localStorage 读 |
| §九 D1 | 更新为"managed_entries 存前端 localStorage" |

### 5. `DESIGN_DATA_CLEANUP.md`

| 位置 | 改什么 |
|------|--------|
| §2.2 允许存储 | 加：`lastDatabase`（上次使用的 database name）、`decisions:{name}`（每个 database 的用户决策）、`results:{name}`（每个 database 的计算结果摘要） |
| §3.3 页面切换数据流（若有） | 删 workspace API 引用。改为：compute 时前端从 localStorage 取 decisions → 传参；成功后写 results 回 localStorage |
| §3.4 恢复流程表 | 重写：DataSourcePage → persistence 表单 + localStorage.lastDatabase 恢复下拉；ForestPage → localStorage.results:{name} 恢复摘要；ConflictsPage → localStorage.decisions:{name}.branch_decisions；OperationsPage → localStorage.results:{name} 摘要 |
| §六 决策记录 | D2 更新为"decisions/results 存前端 localStorage，非后端 workspace" |

### 6. `DESIGN_ORCHESTRATOR.md`

| 位置 | 改什么 |
|------|--------|
| §三 compute()/run() 签名 | 确认不接收 workspace 相关参数。`managed_entries` 和 `branch_decisions` 作为可选参数直接接收 |
| §四 内部流程 | 不需要 step 0 读 workspace。orchestrator 内部通过 bootstrap 获取 database 和 user_config |

### 7. `DESIGN_EXECUTION_PLAN.md`

| 位置 | 改什么 |
|------|--------|
| §一 数据模型终态表 | workspace.json 列标注"已撤销——用户决策迁移至前端 localStorage" |
| §一 关键 API 数据流 | 删 workspace 行。加 `POST /api/pipeline/compute → 接受 managed_entries?, branch_decisions?` |
| Phase 1 任务列表 | 删 1.1（新增 workspace.py）、1.6（routes/workspace.py）相关步骤 |
| §四 D1/D6/D12 | 更新为方案 B 的终版结论 |

### 8. `DESIGN_COMM_PROTOCOL.md`

| 位置 | 改什么 |
|------|--------|
| 端点清单表 | 删 workspace 行；`/api/database/load` → `/api/database/read`；补充缺失端点：`/api/rules/aggregate`、`/api/rules/affected-entries`、`/api/rules/load-aggregated` |

### 9. `DESIGN_GUI_DATASOURCE_TAB.md`

| 位置 | 改什么 |
|------|--------|
| 全文检查 | 确认无 workspace.inputs 引用。若有 → 删除 |
| §7 D2 | 已更新过（"重复条目 DataSourcePage 纯展示，裁决移入 ComputePrepPage"）——确认无误 |

### 10. `DESIGN_RULE_AGGREGATOR.md`

| 位置 | 改什么 |
|------|--------|
| 已在上轮修正（删 user_config_path）。无需再改。 | — |

### 11. `repo_spec/user_config.schema.json`

| 位置 | 改什么 |
|------|--------|
| 删除 | `database_output_path` 字段 |
| 新增 | `databases` 字段：type `object`，additionalProperties 为 `{ type: "object", required: ["path"], properties: { path: { type: "string" } } }` |

---

## 执行顺序

1. `DESIGN_WORKSPACE_STATE.md` → 归档 + 重命名为 `DESIGN_GUI_WORKSPACE.md` + 重写
2. `DESIGN_STORAGE.md`
3. `DESIGN_REST_API.md`
4. `DESIGN_GUI.md`
5. `DESIGN_COMPUTE_PREP_PAGE.md`
6. `DESIGN_DATA_CLEANUP.md`
7. `DESIGN_ORCHESTRATOR.md`
8. `DESIGN_EXECUTION_PLAN.md`
9. `DESIGN_COMM_PROTOCOL.md`
10. `DESIGN_GUI_DATASOURCE_TAB.md`（检查性修改）
11. `repo_spec/user_config.schema.json`

---

## 验收标准

| 验收项 | 条件 |
|-------|------|
| workspace 端点 | `grep -rn "workspace/save\|workspace/status" repo_memo/DESIGN_*.md` 返回空（除新 GUI_WORKSPACE 中的历史说明） |
| workspace.json 文件引用 | `grep -rn "workspace\.json" repo_memo/DESIGN_*.md` 仅在 STORAGE.md 的"已撤销"说明和 GUI_WORKSPACE.md 中出现 |
| database 参数名 | `grep -rn "database.*Any\|database_path\|output_path\|cache_path\|user_config_path" repo_memo/DESIGN_REST_API.md`（除历史说明）返回空 |
| databases 字段一致 | `grep -rn "database_output_path\|custom_databases" repo_memo/DESIGN_*.md` 返回空 |
| localStorage 结构 | `GUI_WORKSPACE.md` 和 `DATA_CLEANUP.md` 中的 key 命名一致 |
| 无 workspace.inputs | 除 STORAGE 和 GUI_WORKSPACE 的历史说明外，其余文档不出现 |

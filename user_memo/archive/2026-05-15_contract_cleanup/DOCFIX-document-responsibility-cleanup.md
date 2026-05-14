# DOCFIX — 文档职责体系清理与修正

> Status: plan
> Authority: arch
> Created: 2026-05-14
> Source: `work_memo/2026-05-14_decisions.md`（本次讨论全部裁定）
> 原则：一个概念只在一份文档中"定义"（definition），其他文档"引用"（extern）。删"无 XXX"句式。

---

## 一、文档职责分配（修正后）

```
DESIGN_STORAGE.md          ← 唯一定义：所有文件的路径、字段、搜索策略
    ↑ extern
    ├── DESIGN_WORKSPACE_STATE.md   ← workspace.json 结构 + 其 REST API
    ├── DESIGN_RULE_AGGREGATOR.md   ← 聚合规则。引用 STORAGE 获取字段含义
    ├── DESIGN_ORCHESTRATOR.md      ← 流水线调度接口 + 体系架构图
    ├── DESIGN_REST_API.md          ← 所有端点形状。引用 STORAGE 获取路径语义
    ├── DESIGN_GUI.md               ← 页面流、职责、UI 原则
    ├── DESIGN_GUI_DATASOURCE_TAB.md ← DataSourcePage 详细设计
    ├── DESIGN_COMPUTE_PREP_PAGE.md ← ComputePrepPage 详细设计
    ├── DESIGN_DATA_CLEANUP.md      ← 前端持久化边界 + 恢复流程
    └── repo_spec/*.schema.json     ← JSON 字段精确 schema
```

---

## 二、归档

| 文件 | 原因 |
|------|------|
| `repo_memo/DESIGN_PROCESS_OVERVIEW.md` | 内容已被 DESIGN_GUI + DESIGN_WORKSPACE_STATE 覆盖。且存在过时的 managed 描述 |
| `repo_memo/DESIGN_GUI_GAP_CLOSURE.md` | Phase 4 已完成，任务已执行 |

操作方法：复制到 `repo_memo/archive/` 加日期后缀，原位置删除。

---

## 三、文档修正清单

### 3.1 `DESIGN_STORAGE.md` — 文件存储权威

修改内容：
- §2.1 运行产出默认目录表格，确认 Linux workspace 路径 `~/.local/share/kmm/workspace.json`
- §3.1-3.2：确认单级唯一搜索（Linux: `~/.config/kmm/user_config.json`；Windows: `%appdata%/kmm/user_config.json`）。**删除三级搜索合并描述。**
- §3.3：确认 first_use 机制（文件不存在时自动创建空配置，标记 `first_use: true`）
- §3.5 字段表：新增 `custom_databases` 字段

  ```json
  "custom_databases": [
    { "name": "wsl_scan", "path": "/mnt/d/database_wsl.json" }
  ]
  ```

  | 字段 | 类型 | 必需 | 说明 |
  |------|------|:--:|------|
  | `custom_databases` | `object[]` | 否 | 自定义 database 列表。SettingsPage 管理 |
  | `custom_databases[].name` | `string` | 是 | database 名称标识 |
  | `custom_databases[].path` | `string` | 是 | database 文件路径 |

- §4.2：database.json 输出路径优先级明确为仅 `user_config.database_output_path`，不再提 workspace.inputs
- §5：workspace 的路径唯一来源是平台默认位置（§2.1），不在 user_config 中
- §8.3 允许存储的表：删除 `datasource:form` 中的 `databaseOutputPath`
- §8.4 禁止存储的表：确认
- §9 /tmp/ 政策：`/tmp/kmm/kmm_lib_scan_cache.json` 可丢弃。**删除任何将 user_config 或 database 写入 /tmp/ 的允许**
- §10 决策记录：D8 更新为"managed_entries 归属 workspace.decisions"；新增 D11："user_config 搜索策略为单级唯一"

---

### 3.2 `DESIGN_WORKSPACE_STATE.md` — workspace 结构与 API

修改内容：
- **§一 定位**：图中删除"上次扫描参数"。增加 managed_entries 到 decisions
- **§三 JSON 结构**：删除整个 `inputs` 块。`decisions` 新增 `managed_entries`：

  ```json
  {
    "session_updated": "...",
    "decisions": {
      "branch_decisions": { "root_path": "chosen_source" },
      "managed_entries": {
        "game": { "270150": ["/mnt/d/.../RWR"] },
        "mod": { "270150:2606099273": ["/mnt/d/.../mod"] }
      }
    },
    "results": {
      "last_compute": { ... }
    }
  }
  ```

- **§3.1 inputs**：整节删除。替换为一句："workspace 不存储文件路径。文件路径见 DESIGN_STORAGE.md。"
- **§3.2 decisions**：新增 `managed_entries` 字段说明。格式：`{ game: {appid: [path]}, mod: {mixed_id: [path]} }`。值为列表，表达"仅保留这些路径"。不在其中的 appid/mixed_id → 全部保留。
- **§4 REST API**：删除 `POST /api/workspace/save-inputs`（整个 §4.3）。`POST /api/workspace/save-decisions` 扩展为同时接收 `managed_entries`（可选字段）。更新端点总览表。
- **§六 managed_entries 的传递方式**：整节重写——managed_entries 不再作为 compute 参数直接传入，而是持久化在 workspace.decisions 中。orchestrator 从 workspace 读取。
- **§七 Orchestrator 集成**：更新 compute 流程 —— orchestrator 内部调 bootstrap 获取 database 和 workspace
- **§八 与 database.json 的边界**：更新表格，`managed_entries` 从"compute 参数"列移到"workspace.json"列
- **§十 决策记录**：D2 更新为"managed 存储位置 — workspace.decisions.managed_entries"

---

### 3.3 `DESIGN_REST_API.md` — API 端点规范

修改内容：
- **§4 `POST /api/database/generate`**：删除 `cache_path` 参数。请求体：`{ mode, paths?, working_pathstyle, greedy_parsing }`
- **§4 `POST /api/database/load`**：改为 `POST /api/database/current`。请求体为空 `{}`。后端从 user_config 找到 database 路径后返回。描述："获取当前生效的 database 内容。不接收 path 参数——后端从 user_config.database_output_path 定位文件。"
- **§4 `POST /api/database/save`**：删除 `output_path`。请求体：`{ database }`。描述包含"写入 user_config.database_output_path 指定的位置"
- **§4 `POST /api/pipeline/compute`**：`database: Any` 删除。`user_config_path` 删除。请求体变为：

  ```json
  {
    "kmm_rule_paths": ["..."],
    "aggregated_rule_path": "...",
    "action_orders": null,
    "branch_decisions": null,
    "managed_entries": null
  }
  ```

  补充说明："database 和 user_config 由 orchestrator 内部通过 bootstrap 获取。调用方不传入。"
- **§4 `POST /api/pipeline/run`**：同上。删除 `database: Any`、`user_config_path`。保留 `backup_dir?`、`dry_run`
- **§4 `POST /api/pipeline/backup`**：删除 `database`、`user_config_path`。请求体：`{ mapping_result, backup_dir? }`。补充说明："backup_dir 为空时由 orchestrator 内部从 user_config 和 database 推导"
- **§4 `POST /api/pipeline/apply`**：同上。删除 `database`、`user_config_path`
- **§4**：删除 `POST /api/workspace/save-inputs` 端点描述
- **§6 Pydantic Schema**：
  - `GenerateDatabaseRequest`：删除 `cache_path`
  - `LoadDatabaseRequest` → 改为 `CurrentDatabaseRequest`（空 body 或仅 `database_ref?`）
  - `SaveDatabaseRequest`：删除 `output_path`
  - `ComputeRequest`：`database: Any` → 删除；`user_config_path: str` → 删除
  - `RunRequest`：`database: Any` → 删除；`user_config_path: str` → 删除
  - `BackupRequest`：新增 `mapping_result` 字段（当前代码有但文档缺）；`database` → 删除；`user_config_path` → 删除
  - `ApplyRequest`：同上
  - `SaveDecisionsRequest`：新增 `managed_entries: dict | None = None`
  - 删除 `SaveInputsRequest`

---

### 3.4 `DESIGN_ORCHESTRATOR.md` — 流水线调度

修改内容：
- **§一 定位**：架构图修正为：

  ```
                   ┌─────────────────────┐
      CLI / GUI →  │    orchestrator      │  统一调度入口
                   │  (run / compute /    │
                   │   backup / apply)    │
                   └──────────┬──────────┘
                              │ 需要环境数据时调用
                   ┌──────────▼──────────┐
                   │     bootstrap        │  环境初始化
                   │  (user_config /      │
                   │   database /         │  未来：profile 管理
                   │   workspace)         │
                   └──────────┬──────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         aggregator        engine        backup_ops
        (规则聚合)       (映射计算)      (备份/替换/恢复)
  ```

- **§三 compute() 签名**：`database: dict` → 改为 orchestrator 内部从 bootstrap 获取。删除 `user_config_path` 参数
- **§三 run() 签名**：同上。`database: dict` 删除，`user_config_path: str` 删除
- **§四 内部流程**：在"1. 聚合规则"之前增加"0. 环境初始化：bootstrap 获取 user_config + database + workspace"

---

### 3.5 `DESIGN_RULE_AGGREGATOR.md` — 规则聚合

修改内容：
- **§2.2 user_config.json**：整节替换为：

  > user_config 的字段定义与搜索策略见 `DESIGN_STORAGE.md` §3。
  > 聚合器不消费 user_config。调用方需要的是 `kmm_rule_paths` 列表和可选的 `output_path`——这些由上层（orchestrator）传入。

- **§6.2 核心函数签名**：`aggregate()` 删除 `user_config_path` 参数。签名变为：

  ```python
  def aggregate(
      kmm_rule_paths: list[str],
      *,
      action_orders: dict[str, int] | None = None,
      sidecar_refs: dict[...] | None = None,
      output_path: str | None = None,
  ) -> tuple[dict[str, Any] | None, list[str], list[str]]:
  ```

- **§6.3 聚合流程**：步骤 1 "加载 user_config.json（验证 schema）"删除

---

### 3.6 `DESIGN_GUI.md` — 前端 GUI

修改内容：
- **§3.1 DataSourcePage**："无 radio、无 managed 选择、无'确认进入下一步'按钮" → 改为：

  > DataSourcePage 仅展示扫描结果。重复条目客观展示，不做裁决。裁决在计算准备页完成。

- **§3.7 高级**：Database tab 数据来源 `POST /api/database/load` → 改为 `POST /api/database/current`
- **§六 数据流**：
  - `POST /api/workspace/save-inputs` → 删除该行
  - `POST /api/workspace/save-decisions` → 补充说明"同时接收 managed_entries（可选）"
  - `POST /api/pipeline/compute` → 补充说明"不接受 database dict；orchestrator 自行读取"
- **§九 决策记录**：D2 更新为"managed 归属 — workspace.decisions.managed_entries"

---

### 3.7 `DESIGN_COMPUTE_PREP_PAGE.md` — 计算准备页

修改内容：
- **§五.1 请求**：

  ```json
  POST /api/pipeline/compute
  {
    "aggregated_rule_path": "...",
    "branch_decisions": { ... },
    "managed_entries": { ... }
  }
  ```

  删除 `database_path`、`rule_paths`、`user_config_path`。

- **§六 数据流**：
  - 第 234 行 `POST /api/workspace/save-inputs { aggregated_rule_path }` → 删除该步
  - 第 237 行 `GET /api/workspace/status → inputs.aggregated_rule_path` → 改为"从 user_config 或请求参数获取"
  - 第 245 行 `POST /api/pipeline/compute { ..., managed_entries }` → 描述更新：orchestrator 内部获取 database
- **§九 决策记录**：D1 更新为"managed_entries 存储 — workspace.decisions.managed_entries"

---

### 3.8 `DESIGN_DATA_CLEANUP.md` — 数据清理

修改内容：
- **§2.2 允许存储的内容**：删除 `databaseOutputPath`
- **§2.3 禁止存储的内容**：表中删除 `databasePath`（它属于 workspace inputs，不再存在）
- **§3.3 页面切换数据流动**：
  - `POST /api/workspace/save-inputs` → 删除
  - `POST /api/pipeline/compute { database_path?, rule_paths, branch_decisions }` → 改为"不接受 database；orchestrator 内部获取"
- **§3.4 恢复流程表**：重写为：

  | 页面 | 恢复来源 |
  |------|---------|
  | DataSourcePage | persistence（discoveryMode, manualPaths, 可见性）；扫描结果不缓存 |
  | ForestPage | workspace（decisions + results）；database 由 orchestrator 内部获取 |
  | ConflictsPage | workspace.decisions.branch_decisions |
  | OperationsPage | workspace.results.last_compute |
  | SettingsPage | `POST /api/config/discover` → user_config |
  | RulesOverviewPage | `POST /api/config/discover` → user_config.rule_sources → `/api/rules/scan` |

- **§六 决策记录**：D2 更新——`databasePath, rulePaths` 不再属于 workspace inputs（inputs 块已删除）

---

### 3.9 `DESIGN_EXECUTION_PLAN.md` — 执行计划

修改内容：
- **§一**：删除第 32-43 行（第一版"关键 API 数据流"）
- **§一**：修正第 45-54 行（第二版）：

  ```
  POST /api/database/generate        → 返回: { database(无managed), warnings, errors }
  GET  /api/workspace/status         → 返回 workspace.json 全部内容
  POST /api/workspace/save-decisions → 接收 { managed_entries?, branch_decisions }
  POST /api/workspace/save-results   → 接收 { last_compute }
  POST /api/pipeline/compute         → 不接受 database dict 或路径；orchestrator 自行读取
  ```

  （删除 `save-inputs` 行）

- **§四 决策记录**：
  - D1：更新为"managed 归属 — workspace.decisions.managed_entries"
  - D6：更新为"compute 端点 database 参数 — 不接收。orchestrator 内部通过 bootstrap 获取"
  - D12：更新为"save-decisions 范围 — branch_decisions + managed_entries"

---

### 3.10 `DESIGN_GUI_DATASOURCE_TAB.md` — 数据源选项卡

- **检查**：§3.3 "重复条目——纯展示，不做裁决" 已在 2026-05-13 更新——正确，无需修改
- **§3.3 行为**：确认 "重复条目的取舍在计算准备页完成"——保持
- **§7 决策记录** D2："重复 ID 处理——交互式 radio group" → 这条过时了，更新为"重复条目 DataSourcePage 纯展示，裁决移入 ComputePrepPage"

---

### 3.11 `repo_spec/user_config.schema.json`

新增字段：

```json
"custom_databases": {
    "description": "自定义 database 名称→路径映射列表。由 SettingsPage 管理。",
    "type": "array",
    "default": [],
    "items": {
        "type": "object",
        "required": ["name", "path"],
        "additionalProperties": false,
        "properties": {
            "name": {
                "description": "database 的名称标识。",
                "type": "string"
            },
            "path": {
                "description": "database 文件的本地路径。",
                "type": "string"
            }
        }
    }
}
```

同时确认 `rule_sources` 字段已存在。

---

## 四、执行顺序

1. 归档 `DESIGN_PROCESS_OVERVIEW.md` 和 `DESIGN_GUI_GAP_CLOSURE.md`
2. 修正 `DESIGN_STORAGE.md`（基础——其他文档引它）
3. 修正 `DESIGN_WORKSPACE_STATE.md`
4. 修正 `DESIGN_REST_API.md`
5. 修正 `DESIGN_ORCHESTRATOR.md`
6. 修正 `DESIGN_RULE_AGGREGATOR.md`
7. 修正 `DESIGN_GUI.md`
8. 修正 `DESIGN_COMPUTE_PREP_PAGE.md`
9. 修正 `DESIGN_DATA_CLEANUP.md`
10. 修正 `DESIGN_EXECUTION_PLAN.md`
11. 修正 `DESIGN_GUI_DATASOURCE_TAB.md`
12. 修正 `repo_spec/user_config.schema.json`

每完成一份文档，检查是否有引用该文档的其他文档需要同步调整（按 extern 关系）。

---

## 五、验收标准

| 验收项 | 条件 |
|-------|------|
| 无重复定义 | 任意概念（managed_entries, database_path, user_config_path, 恢复流程, user_config 字段）只在唯一一份文档中"定义"，其余引用 |
| 无"无 XXX"句式 | `grep -r "无.*\|不.*选择\|不.*按钮" repo_memo/DESIGN_GUI.md` 返回空 |
| workspace.inputs | `grep -r "workspace.*inputs\|save-inputs" repo_memo/ --include="*.md"` 仅在 `DESIGN_WORKSPACE_STATE.md` 的删除标记中、以及方案文档和裁定记录中出现 |
| 决策一致 | 所有文档中关于 managed_entries 归属的决策记录一致指向 `workspace.decisions` |

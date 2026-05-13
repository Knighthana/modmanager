# DESIGN_WORKSPACE_STATE — 后端工作区状态

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义后端 workspace.json 的结构、REST API 端点、生命周期与单工作区覆盖策略。作为"用户 branch 决策与上次计算结果"在后端的权威存储。
> 创建：2026-05-13
> 更新：2026-05-13 — 【重大简化】移除 managed_entries（改为 compute 可选参数，不在 workspace 中）；decisions 仅保留 branch_decisions；results 不存完整 trees，仅摘要 + inputs_hash

---

## 一、定位

`workspace.json` 是当前工作会话中用户的 branch 决策与上次计算结果的持久化文件。

```
database.json          workspace.json         user_config.json
┌──────────────┐      ┌──────────────────┐   ┌─────────────────┐
│ 磁盘的客观描述 │      │ 分支决策 + 计算结果 │   │ 工具的行为配置   │
│              │      │                  │   │                 │
│ steamlib[]   │      │ decisions:       │   │ bakprefix       │
│ game[]       │      │   branch_decisions│  │ bakignore[]     │
│ mod[]        │      │                  │   │ database_output │
│              │      │ inputs:          │   │ _path           │
│ (无managed   │      │   上次扫描参数    │   │ ...             │
│  无warnings  │      │                  │   │                 │
│  无errors)   │      │ results:         │   │                 │
│              │      │   上次计算结果摘要 │   │                 │
└──────────────┘      └──────────────────┘   └─────────────────┘
```

---

## 二、文件位置

| 平台 | 路径 |
|------|------|
| Linux | `~/.local/share/kmm/workspace.json` |
| Windows | `%localappdata%/kmm/workspace.json` |

**单例**：始终只有一份 `workspace.json`，新操作覆盖旧状态。不支持多 session。

---

## 三、JSON 结构

```json
{
  "session_updated": "2026-05-13T15:30:00Z",
  "inputs": {
    "database_path": "/tmp/modmanager_database_generated.json",
    "rule_paths": ["/home/user/kmm_rules/"],
    "aggregated_rule_path": "/tmp/aggregated_rule_set.json",
    "user_config_path": "~/.config/kmm/user_config.json",
    "discovery_mode": "all",
    "discovery_manual_paths": []
  },
  "decisions": {
    "branch_decisions": {}
  },
  "results": {
    "last_compute": {
      "trees_count": 0,
      "mapping_count": 0,
      "warnings": [],
      "errors": [],
      "stats": {},
      "inputs_hash": "",
      "timestamp": null
    }
  }
}
```

### 3.1 `inputs`

存储上次 pipeline 使用的参数。前端刷新页面后据此恢复表单状态。

| 字段 | 类型 | 说明 |
|------|------|------|
| `database_path` | `string` | 上次使用的 database.json 路径 |
| `rule_paths` | `string[]` | 上次使用的 rule 文件路径列表 |
| `aggregated_rule_path` | `string` | 上次聚合产出的 aggregated_rule_set.json 路径 |
| `user_config_path` | `string` | 上次使用的 user_config.json 路径 |
| `discovery_mode` | `"auto" \| "manual" \| "all"` | 上次扫描模式 |
| `discovery_manual_paths` | `string[]` | 上次手动指定路径列表 |

### 3.2 `decisions`

仅包含 branch_decisions。**不包含 managed_entries。**

#### branch_decisions

记录用户在 ConflictsPage 上对分枝树的选择。由 ConflictsPage [确认决策] 按钮触发保存。

```json
{
  "branch_decisions": {
    "/path/to/tree/root/a": "/path/to/source/m1",
    "/path/to/tree/root/b": "/path/to/source/m2"
  }
}
```

| key | value |
|-----|-------|
| tree `root_path` | 用户选中的 source `root_path` |

### 3.3 `results`

存储上次 pipeline compute 的结果摘要。

| 字段 | 类型 | 说明 |
|------|------|------|
| `trees_count` | `int` | 树总数 |
| `mapping_count` | `int` | final_mapping 条目数 |
| `warnings` | `string[]` | compute 警告 |
| `errors` | `string[]` | compute 错误 |
| `stats` | `object` | 其他统计信息 |
| `inputs_hash` | `string` | 产生此结果的输入指纹（hash of database_path + rule_paths + branch_decisions + managed_entries） |
| `timestamp` | `string \| null` | 上次计算时间（ISO 8601） |

> **不存储完整 trees / mapping**。完整数据体积大，会导致其他 workspace 消费者（Settings、DataSource 等）加载缓慢。完整 trees 由前端 Pinia 内存持有（跨 tab 不丢，刷新后自动重新 compute）。

---

## 四、REST API

### 4.1 端点总览

| 方法 | 路径 | 作用 | 调用者 |
|------|------|------|--------|
| `GET` | `/api/workspace/status` | 获取 workspace.json 全部内容 | 前端加载/刷新时 |
| `POST` | `/api/workspace/save-inputs` | 更新 inputs 块 | DataSourcePage 扫描后、RulesOverview 聚合后、ForestPage 参数变更后 |
| `POST` | `/api/workspace/save-decisions` | 更新 branch_decisions | ConflictsPage [确认决策] |
| `POST` | `/api/workspace/save-results` | 更新 results 块 | 计算准备页 compute 成功后 |

### 4.2 `GET /api/workspace/status`

无请求体。响应：

```json
{
  "ok": true,
  "data": {
    "session_updated": "2026-05-13T15:30:00Z",
    "inputs": { ... },
    "decisions": { ... },
    "results": { ... }
  }
}
```

若 `workspace.json` 不存在，返回默认空结构 + `first_use: true`。

### 4.3 `POST /api/workspace/save-inputs`

```json
{
  "database_path": "...",
  "rule_paths": ["..."],
  "aggregated_rule_path": "...",
  "user_config_path": "...",
  "discovery_mode": "auto",
  "discovery_manual_paths": []
}
```

所有字段可选——仅传入需要更新的字段，未传入的保留原值。

### 4.4 `POST /api/workspace/save-decisions`

```json
{
  "branch_decisions": {
    "/path/to/tree/a": "/path/to/source/m1"
  }
}
```

传入的值**合并**到现有 decisions 中。传入 `null` 的键表示删除该决策。

> **仅接收 branch_decisions**。managed_entries 不作为独立 API——它随 compute 请求直接传入。

### 4.5 `POST /api/workspace/save-results`

```json
{
  "trees_count": 42,
  "mapping_count": 15,
  "warnings": ["W_LOCAL_MOD_MISSING: ..."],
  "errors": [],
  "stats": { "total_actions": 150 },
  "inputs_hash": "abc123"
}
```

由计算准备页 compute 成功后自动调用。后端写入 workspace.json 的 results 块。

---

## 五、生命周期

### 5.1 创建

`GET /api/workspace/status` 发现文件不存在时，自动创建默认空结构。

### 5.2 更新

任何 `POST /api/workspace/save-*` 调用：
1. 读入现有 workspace.json
2. 合并传入字段（merge）
3. 更新 `session_updated`
4. 原子写入（temp + rename）

### 5.3 清理

无自动清理。用户可手动删除文件重置工作区。

---

## 六、managed_entries 的传递方式

**不走 workspace。** 由计算准备页 checkbox 状态构建，作为 `POST /api/pipeline/compute` 的可选参数直接传入：

```json
POST /api/pipeline/compute
{
  "database_path": "...",
  "rule_paths": ["..."],
  "branch_decisions": { ... },
  "managed_entries": {
    "game": {
      "270150": ["/mnt/d/.../RWR"]
    },
    "mod": {
      "270150:2606099273": ["/mnt/d/.../mod"]
    }
  }
}
```

orchestrator 行为：
1. 若有 managed_entries → 按列表过滤 database（不在列表中的条目移除）
2. 若某 appid/mixed_id 不在 managed_entries 中 → 全部保留（用户未干预）
3. 若无 managed_entries → database 原样传入 engine

---

## 七、Orchestrator 集成

### compute 流程

```
POST /api/pipeline/compute { aggregated_rule_path?, database_path?, rule_paths?, branch_decisions?, managed_entries? }
  → orchestrator 读 database.json
  → 若 aggregated_rule_path → 直接加载（跳过聚合）
  → 若 kmm_rule_paths → 旧流程：先聚合（向后兼容）
  → 若两者都为空 → 返回 E_NO_RULE_INPUT 错误
  → 若 managed_entries 存在 → 过滤 database
  → 读取 workspace.json.decisions.branch_decisions（若请求中未传）
  → engine.compute_mapping(filtered_database, aggregated_rule_set, branch_decisions)
  → 返回 trees + mapping + warnings + errors
```

### orchestrator 新增函数

```python
def _apply_managed_filter(
    database: dict[str, Any],
    managed_entries: dict[str, dict[str, list[str]]] | None
) -> dict[str, Any]:
    """用 managed_entries 过滤 database。
    
    若 managed_entries 为 None → 返回原 database。
    对 game[]：若 managed_entries.game[appid] 存在 → 仅保留 basepath 在列表中的条目。
    对 mod[]：若 managed_entries.mod[mixed_id] 存在 → 仅保留 path 在列表中的条目。
    """
```

---

## 八、与 database.json 的边界

| 内容 | database.json | workspace.json | compute 参数 |
|------|:---:|:---:|:---:|
| steamlib[] / game[] / mod[] | ✅ | — | — |
| branch 决策 | — | ✅ decisions | ✅（覆盖） |
| managed 预选 | — | — | ✅（可选参数） |
| 扫描参数 | — | ✅ inputs | — |
| compute 结果摘要 | — | ✅ results | — |
| 完整 trees / mapping | —（API 响应） | — | — |

---

## 九、错误处理

| 场景 | 行为 |
|------|------|
| workspace.json 不存在 | 自动创建默认空结构 |
| workspace.json 损坏 | 备份为 `.bak`，创建新文件 |
| 写入时磁盘满 | 返回 500，不损坏现有文件（原子写入） |

---

## 十、决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | 多 session vs 单工作区 | 单工作区 |
| D2 | managed 存储位置 | 不在 workspace 中——作为 compute 可选参数 |
| D3 | branch_decisions 保存时机 | ConflictsPage [确认决策] 按钮触发 POST |
| D4 | results 存储粒度 | 仅摘要 + inputs_hash，不存完整 trees |
| D5 | 写入策略 | 原子写入 |
| D6 | save-decisions 接收范围 | 仅 branch_decisions |

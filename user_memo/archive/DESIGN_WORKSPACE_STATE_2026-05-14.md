# DESIGN_WORKSPACE_STATE — 后端工作区状态

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义后端 workspace.json 的结构、REST API 端点、生命周期与单工作区覆盖策略。作为"用户 branch 决策、managed_entries 预选与上次计算结果"在后端的权威存储。
> 创建：2026-05-13
> 更新：2026-05-14 — 【DOCFIX】移除 inputs 块；managed_entries 迁入 workspace.decisions；save-decisions 扩展为同时接收 managed_entries；更新边界表格与决策记录

---

## 一、定位

`workspace.json` 是当前工作会话中用户的 branch 决策、managed_entries 预选与上次计算结果的持久化文件。

```
database.json          workspace.json         user_config.json
┌──────────────┐      ┌──────────────────┐   ┌─────────────────┐
│ 磁盘的客观描述 │      │ 决策 + 计算结果    │   │ 工具的行为配置   │
│              │      │                  │   │                 │
│ steamlib[]   │      │ decisions:       │   │ bakprefix       │
│ game[]       │      │   branch_decisions│  │ bakignore[]     │
│ mod[]        │      │   managed_entries │  │ database_output │
│              │      │                  │   │ _path           │
│ (无managed   │      │ results:         │   │ ...             │
│  无warnings  │      │   上次计算结果摘要 │   │                 │
│  无errors)   │      │                  │   │                 │
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
  "decisions": {
    "branch_decisions": {},
    "managed_entries": {
      "game": { "270150": ["/mnt/d/.../RWR"] },
      "mod": { "270150:2606099273": ["/mnt/d/.../mod"] }
    }
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

workspace 不存储文件路径。文件路径见 `DESIGN_STORAGE.md`。

### 3.2 `decisions`

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

#### managed_entries

记录用户在计算准备页对重复条目的预选结果。

```json
{
  "managed_entries": {
    "game": { "270150": ["/mnt/d/.../RWR"] },
    "mod": { "270150:2606099273": ["/mnt/d/.../mod"] }
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `game` | `dict[str, list[str]]` | appid → 保留路径列表。不在其中的 appid → 全部保留 |
| `mod` | `dict[str, list[str]]` | mixed_id → 保留路径列表。不在其中的 mixed_id → 全部保留 |

### 3.3 `results`

存储上次 pipeline compute 的结果摘要。

| 字段 | 类型 | 说明 |
|------|------|------|
| `trees_count` | `int` | 树总数 |
| `mapping_count` | `int` | final_mapping 条目数 |
| `warnings` | `string[]` | compute 警告 |
| `errors` | `string[]` | compute 错误 |
| `stats` | `object` | 其他统计信息 |
| `inputs_hash` | `string` | 产生此结果的输入指纹（hash of branch_decisions + managed_entries 等 compute 关键参数） |
| `timestamp` | `string \| null` | 上次计算时间（ISO 8601） |

> **不存储完整 trees / mapping**。完整数据体积大，会导致其他 workspace 消费者（Settings、DataSource 等）加载缓慢。完整 trees 由前端 Pinia 内存持有（跨 tab 不丢，刷新后自动重新 compute）。

---

## 四、REST API

### 4.1 端点总览

| 方法 | 路径 | 作用 | 调用者 |
|------|------|------|--------|
| `GET` | `/api/workspace/status` | 获取 workspace.json 全部内容 | 前端加载/刷新时 |
| `POST` | `/api/workspace/save-decisions` | 更新 branch_decisions 和 managed_entries | ConflictsPage [确认决策]、计算准备页 |
| `POST` | `/api/workspace/save-results` | 更新 results 块 | 计算准备页 compute 成功后 |

### 4.2 `GET /api/workspace/status`

无请求体。响应：

```json
{
  "ok": true,
  "data": {
    "session_updated": "2026-05-13T15:30:00Z",
    "decisions": { ... },
    "results": { ... }
  }
}
```

若 `workspace.json` 不存在，返回默认空结构 + `first_use: true`。

### 4.3 `POST /api/workspace/save-decisions`

```json
{
  "branch_decisions": {
    "/path/to/tree/a": "/path/to/source/m1"
  },
  "managed_entries": {
    "game": { "270150": ["/mnt/d/.../RWR"] },
    "mod": { "270150:2606099273": ["/mnt/d/.../mod"] }
  }
}
```

传入的值**合并**到现有 decisions 中。传入 `null` 的键表示删除该决策。
`managed_entries` 为可选字段——不传时不影响现有值。

### 4.4 `POST /api/workspace/save-results`

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

managed_entries 持久化在 `workspace.decisions.managed_entries` 中。由计算准备页 checkbox 状态构建，通过 `POST /api/workspace/save-decisions` 写入。

orchestrator 在 compute 时从 workspace 读取 managed_entries，与 database 和 branch_decisions 一并传入 engine：

1. orchestrator 内部调用 bootstrap 获取 database 和 workspace
2. 从 workspace.decisions 读取 managed_entries 和 branch_decisions
3. 若有 managed_entries → 按列表过滤 database（不在列表中的条目移除）
4. 若某 appid/mixed_id 不在 managed_entries 中 → 全部保留（用户未干预）
5. 若无 managed_entries → database 原样传入 engine

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

## 七、Orchestrator 集成

### compute 流程

```
POST /api/pipeline/compute { aggregated_rule_path?, branch_decisions?, managed_entries? }
  → orchestrator 内部调用 bootstrap 获取 database + user_config + workspace
  → 若 aggregated_rule_path → 直接加载（跳过聚合）
  → 若 kmm_rule_paths → 旧流程：先聚合（向后兼容）
  → 若两者都为空 → 返回 E_NO_RULE_INPUT 错误
  → 从 workspace.decisions 读取 managed_entries（若请求中未传）
  → 若有 managed_entries 存在 → 过滤 database
  → 从 workspace.decisions 读取 branch_decisions（若请求中未传）
  → engine.compute_mapping(filtered_database, aggregated_rule_set, branch_decisions)
  → 返回 trees + mapping + warnings + errors
```

---

## 八、与 database.json 的边界

| 内容 | database.json | workspace.json | compute 参数 |
|------|:---:|:---:|:---:|
| steamlib[] / game[] / mod[] | ✅ | — | — |
| branch 决策 | — | ✅ decisions | ✅（覆盖） |
| managed 预选 | — | ✅ decisions.managed_entries | ✅（覆盖） |
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
| D2 | managed 存储位置 | workspace.decisions.managed_entries |
| D3 | branch_decisions 保存时机 | ConflictsPage [确认决策] 按钮触发 POST |
| D4 | results 存储粒度 | 仅摘要 + inputs_hash，不存完整 trees |
| D5 | 写入策略 | 原子写入 |
| D6 | save-decisions 接收范围 | branch_decisions + managed_entries |

# DESIGN_WORKSPACE_STATE — 后端工作区状态

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义后端 workspace.json 的结构、REST API 端点、managed_entries 格式、生命周期与单工作区覆盖策略。作为"用户决策与上次计算结果"在后端的唯一权威存储。
> 创建：2026-05-13
> 依赖：此文档的落地将取代 database.json 中的 managed/warnings/errors 字段及前端 localStorage 中的业务数据副本。

---

## 一、定位

`workspace.json` 是用户在当前工作会话中的**主观决策与计算结果**的持久化文件。它与 `database.json`（纯磁盘扫描数据）严格分离，共同构成 pipeline 的完整输入。

```
database.json          workspace.json         user_config.json
┌──────────────┐      ┌──────────────────┐   ┌─────────────────┐
│ 磁盘的客观描述 │      │ 用户的主观决策     │   │ 工具的行为配置   │
│              │      │                  │   │                 │
│ steamlib[]   │      │ decisions:       │   │ bakprefix       │
│ game[]       │      │   managed_entries│   │ bakignore[]     │
│ mod[]        │      │   branch_decisions│  │ database_output │
│              │      │                  │   │ _path           │
│ (无managed   │      │ inputs:          │   │ ...             │
│  无warnings  │      │   上次扫描参数    │   │                 │
│  无errors)   │      │                  │   │                 │
│              │      │ results:         │   │                 │
│              │      │   上次计算结果    │   │                 │
└──────────────┘      └──────────────────┘   └─────────────────┘
```

---

## 二、文件位置

| 平台 | 路径 |
|------|------|
| Linux | `~/.local/share/kmm/workspace.json` |
| Windows | `%localappdata%/kmm/workspace.json` |

**单例**：始终只有一份 `workspace.json`，新操作覆盖旧状态。不支持多 session。若用户需切换工作上下文，应手动管理 workspace 文件。

---

## 三、JSON 结构

```json
{
  "session_updated": "2026-05-13T15:30:00Z",
  "inputs": {
    "database_path": "/tmp/modmanager_database_generated.json",
    "rule_paths": ["/home/user/kmm_rules/", "/home/user/kmm_rules/extra/"],
    "user_config_path": "~/.config/kmm/user_config.json",
    "discovery_mode": "all",
    "discovery_manual_paths": []
  },
  "decisions": {
    "managed_entries": {
      "game": {},
      "mod": {}
    },
    "branch_decisions": {}
  },
  "results": {
    "last_compute": {
      "trees_count": 0,
      "mapping_count": 0,
      "warnings": [],
      "errors": [],
      "stats": {},
      "timestamp": null
    }
  }
}
```

### 3.1 `inputs`

存储上次 pipeline 计算使用的参数。前端刷新页面后据此恢复 ForestPage 表单状态。

| 字段 | 类型 | 说明 |
|------|------|------|
| `database_path` | `string` | 上次使用的 database.json 路径 |
| `rule_paths` | `string[]` | 上次使用的 rule 文件/目录路径列表 |
| `user_config_path` | `string` | 上次使用的 user_config.json 路径 |
| `discovery_mode` | `"auto" \| "manual" \| "all"` | 上次扫描模式 |
| `discovery_manual_paths` | `string[]` | 上次手动指定路径列表 |

### 3.2 `decisions`

用户的交互式决策。由前端在用户确认后通过 API 写入。

#### managed_entries

记录用户对重复 appid / mixed_id 的取舍。**使用路径匹配（方案 B），不依赖数组索引。**

```json
{
  "managed_entries": {
    "game": {
      "270150": "/mnt/d/SteamLibrary/steamapps/common/RWR"
    },
    "mod": {
      "270150:2606099273": "/mnt/d/SteamLibrary/steamapps/workshop/content/270150/2606099273"
    }
  }
}
```

| key | value |
|-----|-------|
| `game.<appid>` | 用户选中的游戏 `basepath`（完整路径） |
| `mod.<mixed_id>` | 用户选中的 mod `path`（完整路径） |

**匹配逻辑**（orchestrator 层执行）：
1. 读取 `database.json` 中的 `game[]` 和 `mod[]`
2. 对每个 `appid`，若 `managed_entries.game[appid]` 存在 → 仅保留 `basepath` 等于该值的条目
3. 对每个 `mixed_id`，若 `managed_entries.mod[mixed_id]` 存在 → 仅保留 `path` 等于该值的条目
4. 过滤后的 database 传入 `compute_mapping`

> **为什么用路径而非索引**：database 重新扫描后数组顺序可能变化，索引不可靠。路径是 stable identifier。

#### branch_decisions

记录用户在 ConflictsPage 上对分枝树的选择。

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

存储上次 pipeline compute 的结果摘要（供 OperationsPage 概览和 ForestPage 恢复用）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `trees_count` | `int` | Forest 树总数 |
| `mapping_count` | `int` | final_mapping 条目数 |
| `warnings` | `string[]` | compute 过程中产生的警告 |
| `errors` | `string[]` | compute 过程中产生的错误 |
| `stats` | `object` | 其他统计信息（字段由 engine 返回决定） |
| `timestamp` | `string \| null` | 上次计算时间（ISO 8601），`null` 表示从未计算 |

> **注意**：`results` 不包含完整的 `trees` 和 `final_mapping` 数据（这些体积可能很大）。仅存储摘要。前端如需完整数据用于可视化/操作，应重新调用 compute。

---

## 四、REST API

### 4.1 端点总览

| 方法 | 路径 | 作用 | 调用者 |
|------|------|------|--------|
| `GET` | `/api/workspace/status` | 获取 workspace.json 全部内容 | 前端加载/刷新时 |
| `POST` | `/api/workspace/save-inputs` | 更新 inputs 块 | DataSourcePage 扫描后、ForestPage 参数变更后 |
| `POST` | `/api/workspace/save-decisions` | 更新 decisions 块 | DataSourcePage 确认 managed、ConflictsPage "确认决策"按钮 |
| `POST` | `/api/workspace/save-results` | 更新 results 块 | pipeline compute 完成后 |

### 4.2 `GET /api/workspace/status`

**无请求体**。

**响应**：
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

若 `workspace.json` 不存在，返回默认空结构（`first_use: true`）。

**行为**：
- 前端应用启动时调用此端点，据此恢复 UI 状态
- 若 `results.last_compute.timestamp` 非 null → ForestPage 可展示上次计算摘要
- 若 `inputs.user_config_path` 为空 → 未配置，应导航到 SettingsPage（TODO-23）

### 4.3 `POST /api/workspace/save-inputs`

**请求体**：
```json
{
  "database_path": "/tmp/modmanager_database_generated.json",
  "rule_paths": ["/home/user/kmm_rules/"],
  "user_config_path": "~/.config/kmm/user_config.json",
  "discovery_mode": "auto",
  "discovery_manual_paths": []
}
```

所有字段可选——仅传入需要更新的字段，未传入的保留原值。

**响应**：
```json
{ "ok": true, "data": { "saved": true } }
```

**调用时机**：
- DataSourcePage 扫描完成 → 更新 `database_path`、`discovery_mode`、`discovery_manual_paths`
- ForestPage 的 rule_paths 输入变更 → 更新 `rule_paths`
- SettingsPage 修改 user_config 路径 → 更新 `user_config_path`

### 4.4 `POST /api/workspace/save-decisions`

**请求体**：
```json
{
  "managed_entries": {
    "game": { "270150": "/mnt/d/SteamLibrary/steamapps/common/RWR" },
    "mod": { "270150:2606099273": "/mnt/d/SteamLibrary/steamapps/workshop/content/270150/2606099273" }
  },
  "branch_decisions": {
    "/path/to/tree/a": "/path/to/source/m1"
  }
}
```

`managed_entries` 和 `branch_decisions` 均为可选——仅传入需要更新的块。传入的值**合并**到现有 decisions 中（不覆盖未传入的条目）。

> **合并语义**：对 `managed_entries.game`，传入的键覆盖同键旧值，未传入的键保留原值。`branch_decisions` 同理。若要删除某个决策，传入值为 `null`。

**响应**：
```json
{ "ok": true, "data": { "saved": true } }
```

**调用时机**：
- DataSourcePage 用户选择 managed 条目后点击"确认"按钮
- ConflictsPage 用户完成分枝决策后点击"确认决策"按钮
- **不在每次切 radio 时调用**——避免粘滞感和过频 I/O

### 4.5 `POST /api/workspace/save-results`

**请求体**：
```json
{
  "trees_count": 42,
  "mapping_count": 15,
  "warnings": ["W_LOCAL_MOD_MISSING: mod 'xyz' not installed"],
  "errors": [],
  "stats": { "total_actions": 150 }
}
```

**响应**：
```json
{ "ok": true, "data": { "saved": true } }
```

**调用时机**：
- pipeline compute / run 成功完成后，由前端（ForestPage）自动调用
- 后端 orchestrator 不自行调用——decouple 计算结果产生与持久化

---

## 五、生命周期

### 5.1 创建

`GET /api/workspace/status` 发现文件不存在时，自动创建包含默认空结构的 `workspace.json`，`session_updated` 设为当前时间。返回 `first_use: true` 标记。

### 5.2 更新

任何 `POST /api/workspace/save-*` 调用：
1. 读入现有 `workspace.json`（若不存在则创建默认结构）
2. 合并传入字段（merge，非 replace）
3. 更新 `session_updated` 为当前时间
4. 原子写入（先写临时文件再 rename，防止写一半崩溃）

### 5.3 清理

无自动清理。用户可手动删除 `~/.local/share/kmm/workspace.json` 重置工作区。

---

## 六、Orchestrator 集成

### 6.1 compute 流程变更

```
旧：
  POST /api/pipeline/compute { database: dict, ... }
  → orchestrator.compute(database=dict, ...)

新：
  POST /api/pipeline/compute { database_path?: string, rule_paths: [...], ... }
  → orchestrator.compute(database_path=..., ...)
  → orchestrator 读取 database.json
  → orchestrator 读取 workspace.json.decisions.managed_entries
  → orchestrator 用 managed_entries 过滤 database
  → orchestrator 调用 engine.compute_mapping(filtered_database, ...)
```

### 6.2 orchestrator 新增函数

```python
def _apply_managed_filter(
    database: dict[str, Any],
    managed_entries: dict[str, dict[str, str]]
) -> dict[str, Any]:
    """用 managed_entries 过滤 database 中的重复条目。
    
    Args:
        database: 完整的 database 结构（含 game[], mod[]）
        managed_entries: workspace.decisions.managed_entries
        
    Returns:
        过滤后的 database 副本，原对象不被修改
    """
```

过滤规则：
1. 对 `game[]`：若某 appid 在 `managed_entries.game` 中 → 仅保留 `basepath` 匹配的条目；若不在 → 保留所有条目（向后兼容）
2. 对 `mod[]`：若某 mixed_id 在 `managed_entries.mod` 中 → 仅保留 `path` 匹配的条目；若不在 → 保留所有条目

---

## 七、与 database.json 的边界

| 内容 | database.json | workspace.json |
|------|:---:|:---:|
| steamlib[] | ✅ | — |
| game[] （无 managed） | ✅ | — |
| mod[] （无 managed） | ✅ | — |
| managed 决策 | — | ✅ |
| branch 决策 | — | ✅ |
| 扫描参数 | — | ✅ inputs |
| compute 结果摘要 | — | ✅ results |
| warnings / errors | —（API 响应中返回，不写入文件） | ✅ results |

---

## 八、错误处理

| 场景 | 行为 |
|------|------|
| workspace.json 不存在 | 自动创建默认空结构 |
| workspace.json 损坏（非 JSON） | 返回 500 + 错误信息；旧文件备份为 `workspace.json.bak` 后创建新文件 |
| 写入时磁盘满 | 返回 500 + 错误信息；不损坏现有文件（原子写入保证） |
| managed_entries 指向不存在的路径 | 不报错——可能 database 尚未重新扫描。下一次 compute 时该条目自然无法匹配，产生 warning |

---

## 九、实现文件

| 文件 | 职责 |
|------|------|
| `src/modmanager/workspace.py`（新） | workspace.json 的读写、合并、原子写入逻辑 |
| `src/modmanager_web/routes/workspace.py`（新） | 四个 REST 端点 |
| `src/modmanager_web/schemas.py`（改） | 新增 workspace 相关 Pydantic 模型 |
| `src/modmanager_web/app.py`（改） | 注册 workspace 路由 |
| `src/modmanager/orchestrator.py`（改） | 新增 `_apply_managed_filter`；compute 流程适配 |

---

## 十、决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | 多 session vs 单工作区 | 单工作区，始终覆盖 |
| D2 | managed 匹配方式 | 路径匹配（方案 B），不依赖数组索引 |
| D3 | branch_decisions 保存时机 | 按钮触发 POST，非每次切 radio |
| D4 | results 存储粒度 | 仅摘要，不存完整 trees/mapping |
| D5 | compute 端点 database 参数 | 不接受 dict；接受可选 database_path string |
| D6 | 写入策略 | 原子写入（temp + rename） |

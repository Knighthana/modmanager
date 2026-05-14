# DESIGN_GUI_WORKSPACE — 前端用户决策与结果存储

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义前端 workspace 逻辑——用户决策（decisions）和计算结果摘要（results）存储在前端 localStorage 中，不再有后端 workspace.json 文件或 REST API。
> 创建：2026-05-14（原 DESIGN_WORKSPACE_STATE.md 归档重写）
> 更新：2026-05-14（§十二补充裁定：聚合为单一 `modmanager:workspace` key）

---

## 一、定位

Workspace 逻辑已迁移到前端。不再有后端 workspace.json 文件或 workspace REST API 端点。

用户决策（decisions）和计算结果摘要（results）通过 `localStorage` 在前端持久化，使用 `modmanager:` 命名空间前缀。

compute 时，前端从 localStorage 读取 decisions，作为请求参数传入 `POST /api/pipeline/compute`。compute 完成后，前端从响应中提取摘要，写入 localStorage 的 results。

---

## 二、localStorage 存储结构

所有分散的 key（`lastDatabase`、`decisions:{name}`、`results:{name}`、`aggregatedRuleSet`）聚合为单一 `modmanager:workspace` key：

```
modmanager:workspace
```

### 2.1 workspace 结构

```json
{
  "lastDatabase": "default",
  "perDatabase": {
    "default": {
      "decisions": {
        "managed_entries": { ... },
        "branch_decisions": { ... }
      },
      "results": {
        "trees_count": 42,
        "mapping_count": 15,
        "warnings": [],
        "errors": [],
        "stats": {},
        "timestamp": "2026-05-14T12:00:00Z"
      }
    },
    "HOSTB_SSD": {
      "decisions": { ... },
      "results": { ... }
    }
  },
  "aggregatedRuleSet": { ... },
  "aggregatedRuleHash": "abc123"
}
```

### 2.2 顶层字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `lastDatabase` | `string \| null` | 是 | 上次使用的 database name。前端刷新时用于恢复下拉选中 |
| `perDatabase` | `object` | 是 | 按 database name 索引的 decisions 和 results |
| `aggregatedRuleSet` | `object \| null` | 是 | 聚合后的规则集 dict。compute 时作为请求参数传入后端，不传文件路径 |
| `aggregatedRuleHash` | `string \| null` | 是 | 参与聚合的 rule 文件路径+内容的 hash，用于校验规则是否变更 |

### 2.3 `perDatabase[name].decisions`

| 字段 | 类型 | 说明 |
|------|------|------|
| `managed_entries` | `object` | 用户对重复条目的预选结果。格式见下方 |
| `branch_decisions` | `object` | 用户在 ConflictsPage 的分支裁决。`{ root_path: chosen_source_path }` |

`managed_entries` 格式：

```json
{
  "game": { "270150": ["/mnt/d/.../RWR"] },
  "mod": { "270150:2606099273": ["/mnt/d/.../mod"] }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `game` | `dict[str, list[str]]` | appid → 保留路径列表。不在其中的 appid → 全部保留 |
| `mod` | `dict[str, list[str]]` | mixed_id → 保留路径列表。不在其中的 mixed_id → 全部保留 |

### 2.4 `perDatabase[name].results`

| 字段 | 类型 | 说明 |
|------|------|------|
| `trees_count` | `int` | 树总数 |
| `mapping_count` | `int` | final_mapping 条目数 |
| `warnings` | `string[]` | compute 警告 |
| `errors` | `string[]` | compute 错误 |
| `stats` | `object` | 其他统计信息 |
| `timestamp` | `string \| null` | 上次计算时间（ISO 8601） |

> **不存储完整 trees / mapping**。完整数据体积大，完整 trees 由前端 Pinia 内存持有（跨 tab 不丢，刷新后重新 compute）。

### 2.5 `aggregatedRuleHash` 校验逻辑

`aggregatedRuleHash` 由参与聚合的 rule 文件路径 + 文件内容共同计算得出。

ComputePrepPage 加载时：
1. 读取当前 rule sources（来自 user_config.rule_sources），计算文件路径+内容的 hash
2. 比对 workspace.aggregatedRuleHash
3. 一致 → 复用旧 aggregatedRuleSet，不重新聚合
4. 不一致 → 清空 aggregatedRuleSet，提示"规则已变更，请重新聚合"

hash 算法使用 SHA-256，计算方式：
```
hash = SHA-256(concat(sorted(paths)) + concat(sorted(contents)))
```

---

## 三、DatabaseSelector 组件行为

database 下拉组件是前端通用组件，出现在多个页面：

1. **下拉选中值 = 组件本地状态**。不改 localStorage。不改后端文件。
2. **用户点操作按钮时**，选中值作为 `database_name?` 参数传入请求
3. **下拉切换时**检查 `workspace.perDatabase[新name]?.decisions` 是否存在：
   - 存在 → 提示"恢复上次决策"
   - 不存在 → 提示"无历史决策"
4. **刷新恢复**：读 `workspace.lastDatabase` 恢复选中

---

## 四、compute 流程

```
用户点 [▶ 开始计算]
  → 前端从 workspace.perDatabase[当前 database name].decisions 读 decisions
  → 从 workspace.aggregatedRuleSet 读聚合规则 dict
  → 放入 POST /api/pipeline/compute 请求体
  → 成功 → 从响应提取摘要
  → 写入 workspace.perDatabase[当前 database name].results
```

---

## 五、SettingsPage 改名/删除 database

当用户在 SettingsPage 改名或删除 database 时，前端同步清理/迁移 workspace 中对应的条目：

| 操作 | 行为 |
|------|------|
| 删除 database | 删除 `workspace.perDatabase[name]`；若 `workspace.lastDatabase` 为该 name → 清空 |
| 重命名 database | 将 `workspace.perDatabase[旧name]` → `workspace.perDatabase[新name]`；更新 `workspace.lastDatabase` |

---

## 六、不再包含

- REST API 端点（`/api/workspace/status`、`/api/workspace/save-*`）
- `save-*` 方法
- `merge_workspace`
- 后端文件路径描述

---

## 七、历史说明

原 `DESIGN_WORKSPACE_STATE.md`（已归档至 `archive/DESIGN_WORKSPACE_STATE_2026-05-14.md`）定义了后端 `workspace.json` 的结构与 REST API，该方案在方案 B 中已被撤销。

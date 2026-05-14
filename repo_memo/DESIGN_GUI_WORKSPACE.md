# DESIGN_GUI_WORKSPACE — 前端用户决策与结果存储

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义前端 workspace 逻辑——用户决策（decisions）和计算结果摘要（results）存储在前端 localStorage 中。
> 创建：2026-05-14（原 DESIGN_WORKSPACE_STATE.md 归档重写）
> 更新：2026-05-14（§十二补充裁定：聚合为单一 `modmanager:workspace` key）

---

## 一、定位

Workspace 逻辑由前端 localStorage 承载，不使用后端 workspace 文件或 workspace REST API 端点。

实现约束：workspace 读写入口统一在 `frontend/src/utils/persistence.ts` 的 `loadWorkspace/saveWorkspace`。`frontend/src/stores/workspace.ts` 已移除，不再作为写入口。

用户决策（decisions）和计算结果摘要（results）通过 `localStorage` 在前端持久化，使用 `modmanager:` 命名空间前缀。

compute 时，前端从 localStorage 读取 decisions，作为请求参数传入 `POST /api/pipeline/compute`。compute 完成后，前端从响应中提取摘要，写入 localStorage 的 results。

---

## 二、localStorage 存储结构

所有分散的 key（`lastDatabase`、`decisions:{name}`、`results:{name}`）聚合为单一 `modmanager:workspace` key；聚合规则完整 dict 仅保留在前端内存，localStorage 只保存聚合 metadata：

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
  "aggregatedRuleMeta": {
    "output_path": "/home/user/.config/kmm/aggregated_rule_set.json",
    "aggregated_hash": "abc123",
    "aggregated_at": "2026-05-15T00:00:00Z",
    "selected_rule_paths": ["/rules/r1.kmmrule.json"]
  }
}
```

### 2.2 顶层字段

| 字段 | 类型 | 必需 | 说明 |
|------|------|:----:|------|
| `lastDatabase` | `string \| null` | 是 | 上次使用的 database name。前端刷新时用于恢复下拉选中 |
| `perDatabase` | `object` | 是 | 按 database name 索引的 decisions 和 results |
| `aggregatedRuleMeta` | `object \| null` | 是 | 聚合缓存 metadata（output_path/hash/time/selected_rule_paths），用于刷新后恢复 |

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

### 2.5 `aggregatedRuleMeta.aggregated_hash` 校验逻辑

`aggregatedRuleMeta.aggregated_hash` 由后端聚合结果计算并回传，前端用于快速一致性校验。

ComputePrepPage 加载时：
1. 读取 workspace.aggregatedRuleMeta.aggregated_hash
2. 与当前内存/恢复出的规则集 hash 做比对
3. 内存中有 aggregatedRuleSet → 直接复用
4. 内存 miss 且 workspace.aggregatedRuleMeta.output_path 存在 → 调 `/api/rules/load-aggregated` 恢复
5. 恢复失败或 hash 不一致 → 提示"规则已变更或缓存不可用，请重新聚合"

hash 算法使用 SHA-256（后端计算并回传）。

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
  → 优先从内存读聚合规则 dict；内存 miss 时按 aggregatedRuleMeta.output_path 从后端恢复
  → 放入 POST /api/pipeline/compute 请求体
  → 成功 → 从响应提取摘要
  → 写入 workspace.perDatabase[当前 database name].results
```

---

## 五、SettingsPage 改名/删除 database

当用户在 SettingsPage 改名或删除 database 时，前端同步清理/迁移 workspace 中对应的条目：

| 操作 | 行为 |
|------|------|
| 删除 database | 删除 `workspace.perDatabase[name]`；若 `workspace.lastDatabase` 为该 name → 切到第一个可用 database，若无则置空 |
| 重命名 database | 将 `workspace.perDatabase[旧name]` → `workspace.perDatabase[新name]`；更新 `workspace.lastDatabase` |

---

## 六、不再包含

- REST API 端点（`/api/workspace/status`、`/api/workspace/save-*`）
- `save-*` 方法
- `merge_workspace`
- 后端文件路径描述

---


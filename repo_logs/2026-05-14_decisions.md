# 2026-05-14 架构讨论裁定记录（终版 vFinal — 方案 B）

> 本轮讨论分三个阶段：
> 第一阶段（前半）：裁定 database_path 流转、workspace 职责清理、managed_entries 归属
> 第二阶段（后半）：发现 per_database 嵌套引入新复杂度，追溯 design 本质，最终撤销 workspace.json
> 终版：方案 B — workspace 不存在于后端，全部用户决策存前端 localStorage

---

## 零、开工前 vs 现在：区别一览

| 维度 | 开工前 | 现在（方案 B） |
|------|--------|---------------|
| **workspace.json** | 存在后端文件。含 inputs（6字段）+ decisions + results | **不存在。** 整个文件删除 |
| **workspace API** | `status`、`save-inputs`、`save-decisions`、`save-results` 四个端点 | **全部删除** |
| **managed_entries** | compute 可选参数，不持久化 | localStorage 持久化，compute 时作为参数传入 |
| **branch_decisions** | 存 workspace.decisions，有 API 读写 | localStorage 持久化，compute 时作为参数传入 |
| **lastResults 摘要** | 存 workspace.results，有 API 读写 | localStorage 持久化，纯前端展示 |
| **database_path** | user_config.database_output_path（一个字符串）+ workspace.inputs.database_path（另一个字符串），双存 | user_config.databases（一个对象 `{name: {path}}`），**唯一定义** |
| **user_config.custom_databases** | 不存在（后来加入又撤销） | **不存在。** 被 `databases` 对象替代 |
| **database 参数** | 端点收 `database: Any`（dict 或 path 字符串） | 收 `database_name?: string`（可选，不传则用 localStorage 记录的 lastDatabase） |
| **aggregator 参数** | 收 `user_config_path` | **不收了**——不需要 user_config |
| **user_config 搜索** | 三级搜索合并（代码实际行为） | 单级搜索（对齐 DESIGN_STORAGE.md） |
| **文档职责** | 同一概念多份文档反复定义；DESIGN_GUI.md 有"无XXX"句式；EXECUTION_PLAN 内两份矛盾的 API 流 | 一个概念一份定义，其余 extern 引用；无负向句式；矛盾已清除 |
| **归档文件** | DESIGN_PROCESS_OVERVIEW.md / DESIGN_GUI_GAP_CLOSURE.md 在原位 | 已归档 |
| **架构拓扑** | 图对但代码偏（路由层自己做路径解析再调 orchestrator） | 图对，要求代码对齐（orchestrator → bootstrap，路由层不替 orchestrator 做环境准备） |
| **前端 database 路径持有** | datasourceStore.databaseOutputPath、forestStore.pipelineForm.databasePath | **全部删除。** 下拉选 name，后端查 path |
| **前端跨 store 裸写** | DataSourcePage 直接写 forestStore 字段 | 走 action |
| **database 切换行为** | 无统一机制 | DatabaseSelector 公共组件。下拉选 name → 本地状态 → 请求参数。**不写 localStorage。不写后端文件。无 IO。** |

---

## 一、架构拓扑（确认原始设计）

```
       CLI ──────────────┐
                          ▼
    SettingsPage ──→  Web API ──→ orchestrator（唯一调度入口，星形中心）
                                       │
                                  ┌────┴────┐
                                  ▼         ▼
                              bootstrap   engine
                              (环境初始化) (计算)
                                  │
                              aggregator
                              backup_ops
```

- orchestrator 是入口和管理者，bootstrap 是 orchestrator 的部下
- orchestrator 不知道 workspace、不知道 user_config 持久化、不知道 decisions 从哪来——只收参计算

---

## 二、user_config.json — databases 对象

```json
{
  "databases": {
    "default":   { "path": "~/.local/share/kmm/database.json" },
    "HOSTB_SSD": { "path": "/mnt/f/database_ssd.json" }
  }
}
```

| 规则 | 说明 |
|------|------|
| 对象防重 | JSON 对象天然防重——同名 key 写第二次覆盖 |
| 对象而非字符串 | 每个 entry 是 `{path}` 而非裸字符串——未来扩展字段不 breaking |
| default 可删 | 用户删除后列表为空 → SettingsPage 提供"恢复默认"按钮 |
| 唯一权威 | 所有后端 database 路径查询的唯一来源 |
| 搜索策略 | 单级唯一：Linux `~/.config/kmm/user_config.json`；Windows `%appdata%/kmm/user_config.json`。first_use 自动创建 |

---

## 三、NO workspace.json

- **workspace.json 文件不存在**
- **所有 workspace API 端点不存在**（`save-inputs`、`save-decisions`、`save-results`、`status`）
- orchestrator 不碰 workspace——只收参

---

## 四、前端 localStorage（方案 B 核心）

```
modmanager:lastDatabase          ← "HOSTB_SSD"
modmanager:decisions:default     ← { managed_entries, branch_decisions }
modmanager:decisions:HOSTB_SSD   ← { managed_entries, branch_decisions }
modmanager:results:default       ← { trees_count, mapping_count, ... }
modmanager:results:HOSTB_SSD     ← { trees_count, mapping_count, ... }
```

| 职责 | 说明 |
|------|------|
| `lastDatabase` | 下拉组件恢复上次选中值 |
| `decisions:{name}` | 每个 database 独立的用户决策。compute 时作为请求参数传入后端 |
| `results:{name}` | 每个 database 独立的计算结果摘要。纯前端展示，后端不需要 |
| 不写后端 | decisions 和 results 只存 localStorage，不通过 API 同步到后端 |

---

## 五、前端 DatabaseSelector 公共组件

```
DataSourcePage / ForestPage / ComputePrepPage / AdvancedPage
  ┌─────────────────────────────────────────┐
  │ database: [⬇ default]  [扫描/读取/计算]   │
  │            HOSTB_SSD                      │
  └─────────────────────────────────────────┘
```

- 下拉选项来自 `user_config.databases` 的 keys
- 选中值 = 组件本地状态。**不改 localStorage。不改后端文件。无 IO。**
- 用户点"读取/扫描/计算"时，选中值作为 `database_name?` 参数传入请求
- 下拉切换时：检查 `localStorage["decisions:{新name}"]` 是否存在 → 提示"恢复上次决策"或"无历史决策"
- 刷新恢复：读 `localStorage["lastDatabase"]` 恢复选中

---

## 六、API 端点

| 端点 | 请求体 | 说明 |
|------|--------|------|
| `POST /api/database/generate` | `{ mode, paths?, database_name? }` | database_name 不传 → 用 user_config.databases 的第一个或默认 |
| `POST /api/database/read` | `{ database_name? }` | 同上 |
| `POST /api/database/save` | `{ database, database_name? }` | 同上 |
| `POST /api/pipeline/compute` | `{ database_name?, aggregated_rule_path?, managed_entries?, branch_decisions? }` | orchestrator 内部：查 user_config.databases[name] → load → compute |
| `POST /api/pipeline/run` | 同上 + `{ backup_dir?, dry_run }` | 同上 |
| `POST /api/pipeline/backup` | `{ mapping_result, backup_dir? }` | — |
| `POST /api/pipeline/apply` | `{ final_mapping, backup_dir?, dry_run }` | — |
| `POST /api/config/save` | `{ config }` | 写入 user_config。**不接收 output_path** |

### 已删除的端点
- ~~`POST /api/workspace/save-inputs`~~
- ~~`POST /api/workspace/save-decisions`~~
- ~~`POST /api/workspace/save-results`~~
- ~~`GET /api/workspace/status`~~

---

## 七、aggregator

- 不接收 `user_config_path`——签名中删除
- 输入：`kmm_rule_paths` + 可选 `output_path`
- 文档删重复的 user_config 字段表，改为引用 `DESIGN_STORAGE.md`

---

## 八、profile 切换 — 归 further

---

## 九、wsl_steam_scan.log

- `tools/test_wsl_crossover.py`（诊断脚本，非生产代码）在 CWD 产生

---

## 十、向前兼容性

- 不做旧数据迁移。"没有任何向前兼容性"。不臃肿，不技术债。

---

## 十一、文档体系原则

- 一个概念只在一份文档中"定义"，其余文档"引用"（extern）
- 不写"无 XXX"句式——文档只定义"是什么"
- `DESIGN_STORAGE.md` 是文件路径/字段定义的唯一权威
- `DESIGN_PROCESS_OVERVIEW.md` / `DESIGN_GUI_GAP_CLOSURE.md` 已归档

---

## 十二、补充裁定（2026-05-14 后续讨论）

### 12.1 前端 workspace 聚合

原后端 workspace 的概念迁移到前端 localStorage，分散在多个 key：
`lastDatabase`、`decisions:{name}`、`results:{name}`、`aggregatedRuleSet`。

**裁定**：聚合为单一 `modmanager:workspace` key。语义清晰、一个 snapshot、与文档命名对齐。

```json
modmanager:workspace
{
  "lastDatabase": "default",
  "perDatabase": {
    "default":   { "decisions": { "managed_entries": {...}, "branch_decisions": {...} },
                   "results":   { "trees_count": 42, "mapping_count": 15, ... } },
    "HOSTB_SSD": { "decisions": {...}, "results": {...} }
  },
  "aggregatedRuleSet": {...},
  "aggregatedRuleHash": "abc123"
}
```

### 12.2 compute 端点仅接受 dict

`aggregated_rule_path` 参数从 compute/run 端点和 schema 中删除。compute 永远只接受 `aggregated_rule_set` dict。

理由：文件是备份产物，不是 compute 的输入。前端管理的 dict 是唯一权威。

连锁效应：页面刷新后若无 dict（localStorage 清空），需重新聚合。通过 `aggregatedRuleHash` 校验避免不必要的重新聚合。

### 12.3 `inputs_hash` 校验

前端 localStorage 存储 `aggregatedRuleHash`——参与聚合的 rule 文件路径 + 内容的 hash。

ComputePrepPage 加载时：计算当前 rule sources hash → 与存储比对 → 一致则用旧 dict，不一致则清空提示重新聚合。

### 12.4 `~` 展开归 path_resolver

- `DESIGN_PATH_RESOLVER.md` 补充枚举 `~` 和 `$HOME` 展开
- 规则："凡是来自用户直接输入的路径，必须经过 `path_resolver`"
- `expand_path` 已是 public，各端点统一用 `from modmanager.path_resolver import expand_path`
- 存储时保留原始 `~`，计算时展开——path_resolver 只读不写用户设置
- 唯一修改存储的行为：`_normalize_rule_sources` 补目录末尾 `/`——职权在路由层（保存时）

### 12.5 文档补充确认

| # | 内容 | 裁定 |
|---|------|------|
| 文档1 | aggregate 输出路径可选 | 有值写入+报错；空值不写，前端维护 |
| 文档2 | affected-entries 职责在前端 | 后端是查询服务；前端传 dict 或路径 |
| 文档3 | compute 只接受 dict | 删除路径参数 |
| 文档4 | `~` 展开归 path_resolver | 补充文档枚举 |
| 文档5 | 前端不管后端 aggregate 文件 | 前端只认通信中拿到的结果 |

### 12.6 实现问题分类

| 类别 | 问题 | 数量 |
|------|------|:--:|
| 旧架构残留 | workspace.py 没删干净 | 1 |
| Phase 1-4 施工 bug | 双重前缀、嵌套访问、默认值空、422、collapse、不建目录、SSE/JSON 混淆等 | 10 |
| 文档未覆盖 | 路径中 `~`、无路径时 compute 拒绝 | 2 |

13 个实现问题中，11 个已在本次修复。文档覆盖的 2 个通过上述裁定明确。

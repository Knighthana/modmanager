---
date: 2026-05-14
topic: Architecture Design Finalization, Cleanup, and Freeze Decision
status: FINALIZED
scope: Storage Model, Python/Frontend Architecture, API Stability, Terminology
fixated_into:
  - repo_memo/TERMS_FIELD_FREEZE.md (add 4 new frozen fields)
  - repo_memo/PATTERNS_ENGINEERING.md (add engineering patterns section)
  - repo_memo/DESIGN_PYTHON_LAYERS.md (new)
  - repo_memo/DESIGN_FRONTEND_LAYER_INDEPENDENCE.md (new)
  - repo_memo/DESIGN_REST_API.md (status → partially-stable, cleanup)
  - repo_memo/DESIGN_STORAGE.md (cleanup)
  - repo_memo/DESIGN_EXECUTION_PLAN.md (cleanup)
  - repo_memo/DOCUMENT_GOVERNANCE.md (add frozen decisions section)
cleanup_actions:
  - TERMS_FIELD_FREEZE.md: delete "已废弃字段（禁止使用）" section
  - DESIGN_REST_API.md: delete "forest → trees" migration note in first paragraph
  - DESIGN_STORAGE.md: delete "workspace.json migration to frontend" history
  - DESIGN_EXECUTION_PLAN.md: delete "workspace.json revoked" notes
  - DESIGN_FOREST_MODEL.md: verify no "forest → trees" migration notes
  - DESIGN_RULE_AGGREGATOR.md: verify no historical terminology references
  - DESIGN_ENGINE_INVARIANTS.md: verify no old terminology
  - DESIGN_STEAM_DISCOVERY.md: delete historical terminology references
related_discussions:
  - 2026-05-14 Architecture Audit Session
  - REST API / GUI Tar Pit Analysis
open_items: []
---

# 2026-05-14 架构设计冻结与文档清理

## 一、已冻结的架构决定（不再讨论）

### 1.1 存储三层模型

**Backend Files（后端文件系统）**
- `user_config.json` — 用户配置（bakprefix, bakignore, rule_sources, databases mapping）
- `database.json` — 纯扫描结果（steamlib, game, mod，无 managed/warnings/errors）
- `aggregated_rule_set.json` — 可选的聚合缓存（当 aggregated_ruleset_output_path 配置时）

**Pinia In-Memory（前端会话内存）**
- `useDataSourceStore` — 本次扫描的原始数据（libraries, games, mods, visibility）
- `useComputeStore` — 本次计算会话的树和映射（trees, finalMapping, aggregatedRuleSet）

**localStorage: `modmanager:workspace`（前端持久化）**
```json
{
  "lastDatabase": "default",
  "perDatabase": {
    "default": {
      "selectedRulePaths": ["path/to/rule1.kmmrule.json"],
      "managedEntries": { "game": {...}, "mod": {...} },
      "branchDecisions": { "root_path": "chosen_source" },
      "lastComputeSummary": {
        "treesCount": 0,
        "mappingCount": 0,
        "warnings": [],
        "errors": [],
        "inputsHash": "",
        "timestamp": ""
      }
    }
  },
  "uiState": {
    "sidebarCollapsed": false,
    "activeTab": "datasource",
    "libraryVisibility": {},
    "gameVisibility": {}
  }
}
```

**决定理由**
- Backend files = 权威真相源（长期持久，后端磁盘文件）
- Pinia = 会话工作区（跨页面传递派生数据）
- localStorage = 用户决策 + 摘要（断开时恢复会话，小体积）
- `aggregatedRuleSet` 不进 localStorage（派生数据，体积大，可从 `selectedRulePaths` 重聚合）
- `database` 不进前端持有（权威在磁盘，需要时后端加载）

**禁止再议**：这个分层定型，所有新特性必须按此分类。

---

### 1.2 字段冻结扩展

**新增冻结字段**
```
lastDatabase          — 当前选中的 database name（字符串）
selectedRulePaths     — 用户选定的规则文件路径列表（string[]）
managedEntries        — 用户对重复条目的路径筛选
  格式: { "game": {appid: [path, ...]}, "mod": {mixed_id: [path, ...]} }
branchDecisions       — 冲突裁决的决策映射
  格式: { root_path: chosen_source_path }
```

**冻结现有字段扩展**
```
mixed_id              — "appid:modid" 格式冻结（不动）
contains_libraryfolders_vdf  — 字段名冻结（不动）
trees                 — 树数组的结构冻结（不动）
managed (on game/mod) — 用户决策字段冻结（不动）
```

**禁止再议**：新代码必须使用冻结字段，不接受别名讨论。

---

### 1.3 Python 层分级（可翻译参考实现）

**第 0 层：Protocol Parsers（协议解析）**
- `acf_parser.py`, `vdf_parser.py` — ACF/VDF 文件格式解析
- **翻译规则**：逻辑精确对应 Rust，不允许优化导致行为差异

**第 1 层：Core Business Logic（业务核心）**
- `engine.py` — 映射计算引擎
- `rule_aggregator.py` — 规则聚合
- `steam_scanner.py` — Steam 库发现
- `database_ops.py` — 数据库扫描
- **翻译规则**：逻辑精确对应 Rust，行为等价性保证

**第 2 层：Orchestration（编排）**
- `orchestrator.py` — 流程编排（compute/backup/apply/run）
- `bootstrap.py` — 初始化和加载
- **翻译规则**：业务流程保持，入参出参改为 Rust 类型

**第 3 层：Entry Points（入口）**
- `cli.py` — CLI 入口
- `src/modmanager_web/routes/` — Web API 路由
- **翻译规则**：参考实现，最终由宿主环境（Rust/Tauri）重实现

**禁止再议**：Rust 迁移时遵守此分级，不讨论分层调整。

---

### 1.4 前端框架独立性（框架迁移准备）

**第 1 层：Transport Abstraction（传输适配）**
- `src/api/transport.ts` — 接口定义（`invoke<T>(path, payload)`, `onProgress` callback）
- `src/api/client.ts` — HTTP 实现（当前）
- `src/api/sse.ts` — SSE 实现（当前）
- **迁移规则**：Tauri 时仅改此层的实现，组件零改动

**第 2 层：State Management（状态管理）**
- `src/stores/workspace.ts` — localStorage 代理
- `src/stores/datasource.ts` — 扫描会话
- `src/stores/compute.ts` — 计算会话
- **迁移规则**：与传输无关，Tauri 时零改动

**第 3 层：Components（业务组件）**
- `src/pages/*.vue` — 页面组件
- `src/components/*.vue` — 复用组件
- **迁移规则**：仅依赖 store，不知道网络细节，Tauri 时零改动

**禁止再议**：前端分层已定，新功能必须遵守此边界。

---

### 1.5 工程模式（稳定实践）

**新增稳定模式（本次讨论冻结）**
- **Workspace Store 唯一写者**：Pinia 中的 `useWorkspaceStore` 是 localStorage 的唯一写者，所有页面通过 store action 修改决策，由 store 负责 flush
- **aggregatedRuleSet 内存化**：派生数据，不进 localStorage，仅在 useComputeStore 内存中跨页面传递
- **database 不缓存前端**：权威来源在磁盘，前端需要时调 API，AdvancedPage 调试工具也是按需取，不从 store 持有
- **SSE 用于长操作**：> 500ms 预期时间的操作走 SSE（progress 推送），短查询走 JSON POST

**禁止再议**：新代码必须遵守，违背需要 RFC。

---

### 1.6 REST API 冻结部分

**已冻结（STABLE ✅）**
```
POST /api/database/generate
POST /api/database/read
POST /api/database/save
POST /api/config/discover
POST /api/config/save
POST /api/rules/scan
POST /api/rules/read
POST /api/rules/aggregate
POST /api/rules/affected-entries
POST /api/backups/list
POST /api/backups/inspect

SSE 协议：event: progress|result|error，JSON 数据流
ApiResponse 格式：{ ok, data, errors, warnings }
错误码：E_* 前缀（fatal），W_* 前缀（non-fatal）
```

**禁止再议**：这些端点参数和响应格式相对稳定，变更需 RFC。

---

### 1.7 REST API 条件冻结部分

**暂不冻结（EVOLVING ⚠️）**
```
POST /api/pipeline/compute
POST /api/pipeline/backup
POST /api/pipeline/apply
POST /api/pipeline/run
```

**已知不稳定的参数**
- `managed_entries` — 前端 GUI 决策流程还在原型，format 可能变
- `action_orders` — 是否必须，何时使用，还未确定（GUI 未用）
- `branch_decisions` — 冲突裁决页面还在设计，可能涉及参数扩展
- `mapping_result` / `final_mapping` — Operations 阶段是否需要完整对象回传还是可以用 hash 索引缓存

**冻结条件**：当 `DESIGN_GUI.md` Status 改为 `stable` 时，重新审视管道端点。

**理由**：GUI 流程还在循环，管道端点与 GUI 页面耦合，过早冻结会导致频繁破坏 spec。

**禁止再议**：这是有意的条件冻结，后端开发时参照 `DESIGN_REST_API.md` 中的 "已知不稳定" 章节，先别基于当前 schema 写死逻辑。

---

## 二、清理行动

### 2.1 文档清理清单

以下文档需要删除旧术语的任何提及，仅保留现状定义：

| 文档 | 动作 | 目标 |
|------|------|------|
| TERMS_FIELD_FREEZE.md | 删除"已废弃字段"整节 | 只保留当前冻结字段，无负面知识 |
| DESIGN_REST_API.md | 删除"forest→trees"历史说法 | 直接写 trees，仿佛从来就是这名字 |
| DESIGN_STORAGE.md | 删除"workspace.json迁移"说法 | 直接定义现状：modmanager:workspace 键 |
| DESIGN_EXECUTION_PLAN.md | 删除"workspace.json撤销"说法 | 只说当前状态 |
| DESIGN_FOREST_MODEL.md | 验证+删除旧术语 | 无"forest改trees"说法 |
| DESIGN_RULE_AGGREGATOR.md | 验证+删除旧术语 | 无旧术语说法 |
| DESIGN_ENGINE_INVARIANTS.md | 验证+删除旧术语 | 无旧术语 |
| DESIGN_STEAM_DISCOVERY.md | 验证+删除旧术语 | 无旧术语说法 |

### 2.2 清理后的效果

旧术语从此彻底消失于权威文档，仅在历史审计日志中出现。下次若遇到类似改名需求，是真正的白纸决策，无"禁用词汇表"的心理负担。

---

## 三、后续行动（非本会话）

### 3.1 需新增的设计文档（进 repo_memo/）

1. **DESIGN_PYTHON_LAYERS.md** — 四层分级 + Rust 翻译规则
2. **DESIGN_FRONTEND_LAYER_INDEPENDENCE.md** — 三层框架独立 + transport 接口
3. **DESIGN_AUDIT_LOGS_GOVERNANCE.md** — 审计日志生命周期管理

### 3.2 需更新的文档

1. TERMS_FIELD_FREEZE.md — 新增 4 字段，删除已废弃表
2. PATTERNS_ENGINEERING.md — 新增工程模式章节
3. DESIGN_REST_API.md — 改 status，加 badge，删历史说法
4. DESIGN_STORAGE.md — 删除迁移说法
5. DESIGN_EXECUTION_PLAN.md — 删除撤销说法
6. DOCUMENT_GOVERNANCE.md — 新增冻结决定章节
7. 清理工作 — 4 个文档验证+删除旧术语

---

## 讨论记录

本审计文档记录了 2026-05-14 的架构设计讨论，涉及：
- 存储三层模型的最终定型
- Python 和前端的分层架构设计
- REST API 的冻结策略（部分冻结，部分条件冻结）
- 文档清理规范（彻底移除旧概念，不保留"禁用词汇表"）
- Tauri 2 迁移的最小准备方案

所有决定已转换为 repo_memo/ 的权威设计文档。本审计文档作为冷备份保存，日常工作不读取本文件。

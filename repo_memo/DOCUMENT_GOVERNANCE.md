# 文档治理规则

> Status: stable
> Authority: authoritative
> Read-Tier: always
> Purpose: 定义 repo_memo 的治理规则、读取层级、例外流程与归档边界

## 需求来源优先级
实现与测试的需求来源优先级固定为：
1. Plan 指令
2. `repo_memo/` 中的文档
3. 代码注释
以上三项冲突时按优先级裁决。

## 文档 vs 代码
- 文档是指导性规范，代码跟随文档变更
- 代码可以随文档变更重构，但不反过来推导逻辑
- `description/` 仅作历史样例，不得直接作为实现依据

## 分层读取机制
- `Tier 0 / always-read`：建立最小正确上下文的核心文档；agent 每次开始实现前必须读取
- `Tier 1 / task-scoped`：按模块或任务读取的权威设计文档；仅在任务涉及对应子系统时读取
- `archive/`：历史设计、阶段决策、同步记录；默认不作为当前实现依据，仅在追溯时按需读取
- `further/`：已确认但当前轮次不执行的未来方案；默认不作为当前实现依据
- `repo_bkgd/`：背景解释与机制推导目录；默认忽略，仅允许通过索引点读具体文件

### Tier 0（每次必读）
- `README.md`
- `DOCUMENT_GOVERNANCE.md`
- `DOCUMENT_METADATA.md`
- `PATTERNS_ENGINEERING.md`
- `TERMS_TERMINOLOGY.md`
- `TERMS_FIELD_FREEZE.md`
- `DESIGN_PROCESS_OVERVIEW.md`
- `DESIGN_ENGINE_INVARIANTS.md`

### Tier 1（按任务读取）
- `DESIGN_FOREST_MODEL.md`
- `DESIGN_RULE_AGGREGATOR.md`
- `DESIGN_REST_API.md`
- `DESIGN_BACKUP.md`
- `DESIGN_ORCHESTRATOR.md`
- `DESIGN_PATH_RESOLVER.md`
- `DESIGN_STEAM_DISCOVERY.md`
- `DESIGN_GUI.md`
- `DESIGN_GUI_DATASOURCE_TAB.md`
- `DESIGN_GUI_GAP_CLOSURE.md`
- `FRONTEND_INTEGRATION_CONSTRAINTS.md`

## repo_bkgd 读取门禁
- `repo_bkgd/` 不得作为目录被主动读取或批量扫描。
- 实现任务不得将 `repo_bkgd/` 作为默认上下文来源。
- 仅允许通过 `repo_memo/` 中的索引链接点读具体背景文件。
- 若背景说明与 `repo_memo/` 权威规范冲突，始终以 `repo_memo/` 为准。

## 冲突解决
- `repo_memo/` 与 `description/` 冲突 → 以 `repo_memo/` 为准
- `repo_memo/` 内部文档间冲突 → Plan 裁决
- 未满足需求来源优先级时，任务标记为 blocked

## Plan 授权例外
- 仅当 Plan 明确写出例外范围时，允许临时引用 `description/`
- 例外任务必须写明：授权来源、有效期、影响字段、回收动作
- 例外结束后在 `archive/MEMORY_SYNC_INDEX.md` 追加回收记录

## 执行门禁
- 实现任务必须引用 repo_memo 中的文档路径；缺失路径视为无效
- 涉及字段命名变更时，先更新 TERMS_TERMINOLOGY.md 与相关设计文档，再改代码
- 新建文档遵循 `DOCUMENT_METADATA.md`；至少显式写出 `Purpose`
- 归档判定以“是否仍为当前权威规范”为准，不以“是否已完成实现”单独判定

## 角色与现场信息
- `repo_logs/` 仅用于历史追溯，不参与默认读取与契约裁决
- `work_memo/` 仅用于当前工作现场状态记录，不作为契约权威来源
- Plan 需要排障时可读取 `work_memo/states.md`，但若与 `repo_memo/` 冲突，仍以 `repo_memo/` 为准

## AI Agent 使用约束
- `description/` 目录对 AI agent **禁止**用于推导实现逻辑、Schema 约束或字段定义
- Agent 任务必须以 `repo_memo/` 和 `repo_spec/` 为唯一权威来源
- `description/` 仅由人类管理者在明确指令下被动更新，agent 读取该目录内容时须忽略其规范含义

## 已冻结不再讨论的决定

以下决定帲定了业务界限、字段、架构、工程实践、API 约束，不很害穳次讨论，新特性必须钀帐该决定。

**Category A: 行动不仁罗成并的一类冒箱。私自改业务决定即是破坟 RFC 程序。**

### 存傢三层模式
- **后端文件**：`user_config.json`, `database.json`, (optional) `aggregated_rule_set.json`
- **Pinia（会话内存）**：useDataSourceStore, useComputeStore
- **localStorage**：`modmanager:workspace` (单键，包含用户决策 + 摘要)

**理由**：不破坏此模式的冻结。

### 字段冻结扩展
- `lastDatabase`, `selectedRulePaths`, `managedEntries`, `branchDecisions`
- 以及 其他掲决策歛膺的微偷RM序吧，修改馋敘 RFC。

### Python 分层定位
- 0-2层：业务核心，必须唾确翻译（Rust 避叶改子 幾孜叶改）
- 3层：入口实现，原来容杉沐与氛境。

### 前端框架独立性
- 第 1 层：**咨询适配（什件为 HTTP, 绿剡 Tauri invoke）**
- 第 2-3 层：与递题递他关，Tauri 时零改动。

### 工程模式
- Workspace Store 唯一写者、aggregatedRuleSet 内存化、database 不缓存、SSE 用于长操作

### API 冻结部分
- `/api/database/*`, `/api/config/*`, `/api/rules/*` (除 compute-scoped), `/api/backups/*` → **STABLE**
- `/api/pipeline/*` (载辒鼓位) → **EVOLVING** (等 DESIGN_GUI.md 稳定后重新冻结)
- SSE 协议、ApiResponse 格式、错误码 → **STABLE**

---

## 建诮拒绝素旨

#### 禁止见: 金萬马藪者缚罷的【优化】
- 例: 发现 Python 版本其欖有儫餕判断、Rust 妹拒。
- **理由**：业务邏辑是当前项目的定义，改它会改变行为。

---

## 归档与未来方案边界
- `archive/` 只接收历史设计、阶段决策、迁移记录；其有效规范必须已被主目录文档吸收
- `further/` 只接收未来方案，不得混入历史归档
- 若某设计文档仍定义当前系统行为，即使对应功能已完成，也必须保留在主目录并按任务读取

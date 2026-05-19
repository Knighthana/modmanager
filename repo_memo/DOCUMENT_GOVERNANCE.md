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

## 文档生命周期判定
- `stable` / `active`：可作为当前实现依据，但默认读取仍以入口索引控制
- `draft`：仅在任务明确指向草案时读取
- `archived` / `future`：默认不作为实现依据，除非 Plan 或当前权威文档明确要求追溯
- 若一份文档的状态与目录位置冲突，优先按目录归属和 `Supersedes` 判定，再由 Plan 裁决

## 分层读取机制
- `Tier 0 / always-read`：建立最小正确上下文的核心文档；agent 每次开始实现前必须读取
- `Tier 1 / task-scoped`：按任务包读取的权威设计文档；仅在任务涉及对应子系统时读取
- `repo_logs/`：历史设计、阶段决策、迁移记录；默认不读，仅在追溯或审计时按需读取
- `further/`：已确认但当前轮次不执行的未来方案；默认不作为当前实现依据
- `repo_bkgd/`：背景解释与机制推导目录；默认忽略，仅允许通过索引点读具体文件

### Tier 0（每次必读）
- `README.md`
- `DOCUMENT_GOVERNANCE.md`
- `DOCUMENT_METADATA.md`
- `PATTERNS_ENGINEERING.md`
- `DESIGN_ENGINE_INVARIANTS.md`

### 条件读取（命名/字段/输出结构变更时）
- `TERMS_TERMINOLOGY.md`
- `TERMS_FIELD_FREEZE.md`

### Tier 1（按任务读取）
- `READING_PACKAGES.md`

## Tier 1 包使用原则
- 优先从 `READING_PACKAGES.md` 选择单一任务包
- 每次实现默认只展开一个包；只有跨域问题才允许第二个包
- 包内文档若超过 3 份，先拆包再扩展，不要把包重新长成清单
- 同一轮任务若需要三个以上子域，优先重构任务边界，而不是直接扩大阅读面

## 高权重触发规则
- 涉及备份目录推导、备份恢复或 `backup_dir` 语义时，必须读取 `DESIGN_BACKUP.md`
- 明确涉及 replace service 方案时，必须读取 `further/REPLACE_SERVICE_DESIGN.md`；其他任务不默认读取

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
- 例外结束后 SHOULD 在 `repo_logs/` 记录回收说明

## 执行门禁
- 实现任务必须引用 repo_memo 中的文档路径；缺失路径视为无效
- 涉及字段命名变更时，先更新 TERMS_TERMINOLOGY.md 与相关设计文档，再改代码
- 新建文档遵循 `DOCUMENT_METADATA.md`；至少显式写出 `Purpose`
- 归档判定以“是否仍为当前权威规范”为准，不以“是否已完成实现”单独判定

## 角色与现场信息
- `work_memo/`：当前工作现场状态；排障时按需读取，不作为契约权威来源
- Plan 需要排障时可读取 `work_memo/states.md`，但若与 `repo_memo/` 冲突，仍以 `repo_memo/` 为准

## AI Agent 使用约束
- `description/` 目录对 AI agent **禁止**用于推导实现逻辑、Schema 约束或字段定义
- Agent 任务必须以 `repo_memo/` 和 `repo_spec/` 为唯一权威来源
- `description/` 仅由人类管理者在明确指令下被动更新，agent 读取该目录内容时须忽略其规范含义

## 已冻结不再讨论的决定
以下决定定义当前实现边界。若需变更，MUST 先更新权威文档，再进入代码实施。

### 冻结决定（当前有效）
- 业务数据权威 MUST 位于后端工作区目录（如 `decisions.json`、`mapping.json`）；前端存储 SHOULD 仅承载 UI 偏好与导航状态。
- `repo_memo/` 与 `repo_spec/` MUST 作为实现与契约的权威来源；`description/`、`repo_logs/`、`work_memo/` MUST NOT 用于契约裁决。
- 若文档标记为 superseded 或 archived，该文档 MUST NOT 作为当前实现依据。
- 命名与字段变更 MUST 先更新术语与冻结文档（`TERMS_TERMINOLOGY.md`、`TERMS_FIELD_FREEZE.md`），再修改代码。

### 变更流程约束
- 涉及架构边界、字段归属、API 语义的变更，MUST 在 Plan 或权威设计文档中先完成裁定。
- 未完成文档裁定前，实施任务 SHOULD 标记为 blocked，避免代码先行导致口径漂移。

---

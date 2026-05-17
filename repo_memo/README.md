# repo_memo

> Status: stable
> Authority: authoritative
> Read-Tier: always
> Purpose: 作为 repo_memo 的总入口，定义分层读取方式与各文档的索引关系

本目录是当前有效的实现规范与工程约束入口。

## 目标
- 为 agent 和人类维护者提供可判定的权威文档入口
- 区分当前规范、历史归档与未来方案，避免默认上下文臃肿
- 保持“文档先于实现”的工程约束，同时降低默认读取成本

## 分层读取

### Tier 0 — 每次必读
用于建立最小正确上下文；开始实现前先读这一层。

| 文档 | 用途 |
|---|---|
| `DOCUMENT_GOVERNANCE.md` | 文档治理、分层读取、例外流程 |
| `DOCUMENT_METADATA.md` | 文档元信息制度与新建文档要求 |
| `PATTERNS_ENGINEERING.md` | 工程模式与开发环境约束 |
| `TERMS_TERMINOLOGY.md` | 术语冻结 |
| `TERMS_FIELD_FREEZE.md` | 字段与输出结构冻结 |
| `DESIGN_PROCESS_OVERVIEW.md` | 系统总览与主流程 |
| `DESIGN_ENGINE_INVARIANTS.md` | 引擎不变量与告警码 |

### Tier 1 — 按任务读取
仅在任务涉及对应子系统时读取。

| 文档 | 适用任务 |
|---|---|
| `DESIGN_STEAM_DISCOVERY.md` | Steam 发现、database 扫描 |
| `DESIGN_RULE_AGGREGATOR.md` | 规则聚合 |
| `DESIGN_FOREST_MODEL.md` | 森林模型、映射解析 |
| `DESIGN_ORCHESTRATOR.md` | 编排层、compute/run/restore |
| `DESIGN_BACKUP.md` | backup_dir、备份与恢复 |
| `DESIGN_PATH_RESOLVER.md` | 路径规范化与解析门禁 |
| `DESIGN_REST_API.md` | Web API、SSE、Web 安全约定 |
| `DESIGN_GUI.md` | GUI 总体设计 |
| `DESIGN_GUI_DATASOURCE_TAB.md` | GUI 数据源页 |
| `DESIGN_GUI_EXECUTION_PROTOCOL.md` | GUI 任务流验收、切片交付、字段归属决策卡 |
| `DESIGN_GUI_GAP_CLOSURE.md` | GUI 缺口补齐与后续收敛 |
| `FRONTEND_INTEGRATION_CONSTRAINTS.md` | 前端第三方集成约束与参数约定 |

### 非默认输入

| 目录 | 语义 |
|---|---|
| `archive/` | 历史设计、阶段决策、同步记录；默认不读，追溯时按需读取 |
| `further/` | 已确认但当前不执行的未来方案；默认不读，不作为当前实现依据 |
| `repo_bkgd/` | 背景解释与机制推导；默认不读，仅允许按索引点读具体文件 |
| `repo_logs/` | 工作日志冷备份；仅用于历史追溯 |
| `work_memo/` | 当前工作现场状态；仅供排障，不作契约裁决 |

## 使用顺序
1. 先读 `DOCUMENT_GOVERNANCE.md`
2. 再读 `DOCUMENT_METADATA.md`
3. 再读术语/字段冻结与总览文档
4. 按当前任务选择对应的 Tier 1 设计文档
5. 仅在追溯或审计时进入 `archive/`，仅在规划未来方案时进入 `further/`

## 备注
- `description/` 仅作为用户与 Plan 的沟通目录，不作为默认实现输入
- 历史同步记录已移入 `archive/MEMORY_SYNC_INDEX.md`
- replace-only 边界以 `further/REPLACE_SERVICE_DESIGN.md` 为准
- backup_dir 解耦边界以 `DESIGN_BACKUP.md` 为准

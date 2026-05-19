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
| `DESIGN_ENGINE_INVARIANTS.md` | 引擎不变量与告警码 |

### 条件读取
仅在命名、字段、输出结构、契约口径变化时读取。

| 文档 | 用途 |
|---|---|
| `TERMS_TERMINOLOGY.md` | 术语冻结 |
| `TERMS_FIELD_FREEZE.md` | 字段与输出结构冻结 |

### Tier 1 — 按任务包读取
仅在任务涉及对应子系统时读取；默认先选 1 个包，最多 2 个包。

| 包 | 适用任务 |
|---|---|
| [包 A1](READING_PACKAGES.md#L13) | 采集、规则聚合、森林模型 |
| [包 A2](READING_PACKAGES.md#L21) | 编排、备份、路径解析 |
| [包 A3](READING_PACKAGES.md#L29) | REST API、引擎约束、Python 分层 |
| [包 B1](READING_PACKAGES.md#L37) | GUI 总体、数据源、计算准备 |
| [包 B2](READING_PACKAGES.md#L45) | GUI 任务流、前端集成、Mock 基础设施 |

### 非默认输入

| 目录 | 语义 |
|---|---|
| `repo_logs/` | 历史设计、阶段决策、同步记录与工作日志；追溯时按需读取 |
| `further/` | 已确认但当前不执行的未来方案；默认不读 |
| `repo_bkgd/` | 背景解释与机制推导；默认不读，仅允许按索引点读具体文件 |
| `work_memo/` | 当前工作现场状态；仅供排障，不作契约裁决 |

## 使用顺序
1. 先读 `DOCUMENT_GOVERNANCE.md`
2. 再读 `DOCUMENT_METADATA.md`
3. 再读必要的总览文档；若涉及命名、字段或输出结构变更，再补读 `TERMS_*`
4. 先选 `READING_PACKAGES.md` 中的一个任务包，再读包内文档
5. 按需进入 `repo_logs/` 或 `further/`。

## 高权重触发读取
- 任务涉及 `backup_dir` 结构、`backupinfo.json` 结构或字段冻结时，必须读取 `DESIGN_BACKUP_DIR.md`（通常对应包 A2）
- 任务涉及 backup 执行、差异备份、`.kmmbakignore` 复制或脏状态/冲突检查时，必须读取 `DESIGN_BACKUP_OPS.md`（通常对应包 A2）
- 任务涉及 restore 执行、命中集合、hash 核对或 `force` 语义时，必须读取 `DESIGN_RESTORE_OPS.md`（通常对应包 A2）
- 任务明确涉及 replace service 方案时，必须读取 `further/REPLACE_SERVICE_DESIGN.md`；其他任务不默认读取

## 备注
- `description/` 仅作为用户与 Plan 的沟通目录，不作为默认实现输入

# 文档元信息说明（面向 Agent）

> Status: active
> Authority: authoritative
> Read-Tier: always
> Purpose: 规定 repo_memo 文档的元信息字段、最小模板与新建文档的标注要求

## 目标
本说明用于定义 `repo_memo/` 文档的元信息字段、最小模板与归属判定入口。

## 基本原则
- 按需创建，但必须先标注用途与预期角色。
- 文档去留看用途与状态，不看是否“已完成”。
- 元信息只负责让治理更容易，不阻塞开发。

## 适用范围
- `repo_memo/` 主目录中的规范文档
- `repo_logs/` 中的历史归档文档
- `repo_memo/further/` 中的未来方案文档

## 最小元信息集
所有文档（包括存量文档）均须在开头显式写出以下信息。

- `Status`：`draft` / `active` / `stable` / `archived` / `future`
- `Authority`：`authoritative` / `reference-only`
- `Read-Tier`：`always` / `task-scoped` / `on-demand`
- `Purpose`：一句话说明本文档解决什么问题、服务什么任务
- `Supersedes`：可选；若替代了旧文档或旧方案，在此注明

## 状态语义
- `draft`：草案
- `active`：当前生效文档
- `stable`：冻结的当前权威文档
- `archived`：历史记录，仅供追溯
- `future`：已确认但当前轮次不执行的方案

## 状态流转
- `draft -> active -> stable`
- `active/stable -> archived`
- `future` 只能放在 `further/`；若变成当前计划，先迁回主目录并改为 `active`
- 状态变更时，同步更新目录归属、`Supersedes` 和索引

## 最小模板

```md
# 文档标题

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 说明本文档用于约束哪个模块或阶段
> Supersedes: 可选，填写被替代文档
```

## 目录归属判断
- `repo_memo/`：当前仍定义系统行为或工程约束的权威文档
- `repo_logs/`：历史决策、迁移记录、阶段性实施文档；细则见 `DOCUMENT_GOVERNANCE.md`
- `repo_memo/further/`：已确认但当前轮次不执行的未来方案

## 变更联动
- 状态、目录归属或 `Supersedes` 变化时，同步检查 `README.md`、`DOCUMENT_GOVERNANCE.md` 和相关索引
- `archived` / `future` 文档不进入默认主读路径

## 包级元信息
- `READING_PACKAGES.md` 中的每个包都应写出适用范围与排除范围
- 每个包默认入口不应超过 3 份文档
- 新增包时，同步检查入口索引是否仍保持“默认先选一个包”

## Agent 行为要求
- 创建新文档时，优先判断它是“当前规范”、“历史记录”还是“未来方案”
- 若无法立即判断长期归属，允许先在主目录创建，但必须明确写出 `Purpose`
- 若文档仅为阶段性记录或排障过程，阶段结束后按目录归属判断处理。
- 不得因元信息制度而拒绝创建对当前任务有帮助的文档

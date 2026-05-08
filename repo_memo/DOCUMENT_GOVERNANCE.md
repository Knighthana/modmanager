# 文档治理规则

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

## 冲突解决
- `repo_memo/` 与 `description/` 冲突 → 以 `repo_memo/` 为准
- `repo_memo/` 内部文档间冲突 → Plan 裁决
- 未满足需求来源优先级时，任务标记为 blocked

## Plan 授权例外
- 仅当 Plan 明确写出例外范围时，允许临时引用 `description/`
- 例外任务必须写明：授权来源、有效期、影响字段、回收动作
- 例外结束后在 MEMORY_SYNC_INDEX.md 追加回收记录

## 执行门禁
- 实现任务必须引用 repo_memo 中的文档路径；缺失路径视为无效
- 涉及字段命名变更时，先更新 TERMS_TERMINOLOGY.md 与相关设计文档，再改代码

## AI Agent 使用约束
- `description/` 目录对 AI agent **禁止**用于推导实现逻辑、Schema 约束或字段定义
- Agent 任务必须以 `repo_memo/` 和 `repo_spec/` 为唯一权威来源
- `description/` 仅由人类管理者在明确指令下被动更新，agent 读取该目录内容时须忽略其规范含义

# apply_expectations

> Status: active
> Authority: normative
> Read-Tier: task-scoped
> Purpose: 给测试组提供 apply 与 apply preflight 的最小契约断言入口

## 一、适用范围

本文档只描述 apply / preflight 的测试断言入口。

本文档不负责：

- backup_dir 结构正例
- backupinfo 结构正例
- engine 内部路径推导细节

这些内容分别以 `backupinfo_expectations.md` 与对应设计文档为准。

## 二、apply 正例断言

测试组可以据此断言：

- apply 只消费 file-to-file 输入
- apply 的 dry_run 与正式执行都返回结构化结果对象
- apply 不触碰 `.kmmbakignore`
- apply 的 warning / error 解释以 `TERMS_ERROR_CODES.md` 为准

## 三、preflight 正例断言

测试组可以据此断言：

- preflight 是 orchestrator 的独立子模块
- preflight 产出 manifest，而不是直接执行 apply
- manifest 至少包含 `ok`、`backup_dirs`、`errors`、`warnings`、`timestamp`
- cache 只是优化层；cache 未命中时允许重算，不改变结果语义

## 四、目录输入非法断言

测试组应覆盖目录输入非法场景：

- 当 `final_mapping.path` 以 `/` 结尾时，schema 校验应失败
- 当 `request.path` 以 `/` 结尾且不是 `!` 时，schema 校验应失败
- 非法目录输入的反应以 schema / contract test 为主，不要求 apply 本体为目录输入补充额外语义
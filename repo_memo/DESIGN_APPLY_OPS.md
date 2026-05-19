# DESIGN_APPLY_OPS — Apply 执行设计

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 apply 如何消费 final_mapping 执行文件替换，以及 apply 自身的输入输出与边界

## 一、职责边界

本文档只描述 apply 原语本身。

本文档不负责定义：

- preflight / gate 如何生产
- backup_dir 或 backupinfo 的结构
- engine 如何构造 final_mapping
- restore 如何执行

这些内容分别由 `DESIGN_PREFLIGHT_APPLY.md`、`DESIGN_BACKUP_DIR.md`、
`DESIGN_ENGINE_INVARIANTS.md`、`DESIGN_RESTORE_OPS.md` 负责。

## 二、总原则

### 2.1 apply 是执行原语

- apply 的定义是：根据 `final_mapping` 直接执行文件替换。
- apply 只消费执行输入，不生产前置决策。
- apply 不猜测用户意图，也不补充上游未定义的语义。
- apply 由上层编排命令（例如 `orchestrate_apply()`）调用，不作为工作区入口本身。

### 2.2 apply 只消费文件输入

- apply 只接受 file-to-file 语义。
- `final_mapping` 中的每个目标路径都应表示单个文件，而不是目录。
- 目录输入的合法性由 schema 与测试约束，不在本文档中重复展开来源问题。

### 2.3 apply 不承担 restore 语义

- apply 的目标是替换当前命中的目标文件。
- apply 不负责“恢复到备份时状态”的正确性判定。
- hash 完整性、恢复安全性与更高层冲突裁决，不属于 apply 本体语义。

## 三、执行输入

apply 执行至少需要：

- 当前 `final_mapping`
- `database`
- `user_config`

其中：

- `final_mapping` 定义“要改哪些文件，以及每个文件采用哪个 request”
- `database` 用于推导目标所属实体与相关执行上下文
- `user_config` 用于读取路径配置与备份相关默认项

## 四、输入契约

### 4.1 final_mapping 条目

每个条目至少包含：

- `path`：目标文件绝对路径
- `request`：当前目标的 winning request，或 delete 哨兵请求

### 4.2 路径约束

- `path` 必须表示文件路径，不得以 `/` 结尾。
- `request.path` 必须表示源文件路径，或 delete 哨兵 `!`。
- 对于 file-to-file 语义，apply 不接受“目录作为输入类型”。

### 4.3 非法输入反应

- 若输入不满足 schema 或契约，apply 不应赋予额外目录语义。
- 非法输入的机器可校验约束以 `repo_spec/mapping_output.schema.json` 为准。
- 非法输入的测试行为以 `repo_test/apply_expectations.md` 与后端测试为准。

## 五、最小执行流程

```text
读取 final_mapping / database / user_config
  -> 按执行上下文分组目标
  -> 对每个条目解析 source / target
  -> dry_run 时仅返回 would-apply 结果
  -> 正式执行时按 request.action 执行 create / replace / delete
  -> 汇总 applied / skipped / errors / warnings / diagnostics
```

apply 可以在内部按目录或上下文分组处理条目，但这属于执行细节，不改变其 file-to-file 契约。

## 六、dry_run 语义

### 6.1 dry_run=false

- 正式执行时，apply 对每个命中条目执行实际文件操作。
- 单个条目失败时记录 error，并继续处理其他条目。

### 6.2 dry_run=true

- dry_run 只返回“将会如何处理”的结构化结果，不修改任何文件。
- dry_run 与正式执行应共享尽可能一致的返回字段。
- 差异应只体现于是否实际写盘，以及结果数组中的内容。

## 七、返回契约

apply 返回结构化结果对象，至少包括：

- `ok`
- `applied`
- `skipped`
- `errors`
- `warnings`
- `diagnostics`
- `dry_run`

返回契约的重点是“字段稳定”，而不是某个具体内部数组的实现细节。

## 八、明确不做什么

apply 不负责以下事项：

- 不生产 preflight / gate 结果
- 不定义 preflight manifest 或 cache policy
- 不触碰 `.kmmbakignore`
- 不做 restore 安全性判定
- 不重新裁决 mapping 正确性

## 九、当前实现涉及的主要错误码与警告码

apply 本体至少涉及以下条目：

- `E_APPLY_MISSING_TARGET`
- `E_APPLY_MISSING_SOURCE`
- `W_APPLY_DIR_NO_MATCHED_ENTRIES`
- `W_APPLY_NO_EFFECT`

这些条目的默认严重级别与统一解释，以 `TERMS_ERROR_CODES.md` 为准。

## 十、测试组可据此断言的“应该是什么样”

测试组可以据本文档编写正例与契约断言：

- apply 只消费 file-to-file 输入
- dry_run 与正式执行返回稳定的结构化结果
- `.kmmbakignore` 不属于 apply 的执行范围
- 非法目录输入由 schema 与测试层阻断，不由 apply 本体扩展解释

更高层门禁、缓存策略与 engine 内部路径构造，不属于本文档职责。
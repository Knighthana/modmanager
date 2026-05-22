# DESIGN_PREFLIGHT_APPLY — Apply 前置门禁设计

> Status: active
> Last update: 2026-05-21 — preflight.py as independent module
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 apply 前置 preflight 子模块的职责、manifest 契约、cache policy 与 orchestrator 调用边界

## 一、职责边界

实现文件：`src/modmanager/orchestrator/preflight.py`（orchestrator 子模块）。

本文档描述 apply 前置 preflight 子模块。

本文档不负责定义：

- apply 原语如何执行文件替换
- backup_dir / backupinfo 的结构
- engine 如何生成 final_mapping

这些内容分别由 `DESIGN_APPLY_OPS.md`、`DESIGN_BACKUP_DIR.md`、
`DESIGN_ENGINE_INVARIANTS.md` 负责。

## 二、定位

- preflight 是 orchestrator 的独立子模块。
- preflight 只有一个直接消费者也不改变其边界：它仍然是"前置决策生产者"，不是 apply 内部逻辑。
- preflight 由 `planner_fileops.plan_fileops()` 在 Planner 层调用（原 `orchestrate_apply()` 已不存在）。
  orchestrator 据 preflight manifest 决定是否继续执行原语。

## 三、总原则

### 3.1 preflight 只生产决策信息

- preflight 的产物是 manifest。
- manifest 表示“当前输入在当前时刻的检查结果”。
- preflight 不执行文件替换，不写入 apply 结果，不改动磁盘状态。

### 3.2 preflight 与 apply 解耦

- apply 不生产 manifest。
- preflight 不承担 apply 的文件操作。
- 两者通过稳定的数据契约衔接，而不是共享隐式状态。

### 3.3 cache 是优化层，不是权威层

- manifest 是一次计算结果。
- cache 是对 manifest 的复用策略。
- cache 命中失败或过期时，只能触发重算，不能改变执行语义。

## 四、执行输入

preflight 执行至少需要：

- 当前 `final_mapping`
- `database`
- `user_config`

可选输入：

- cache 配置
- 检查级别配置

## 五、最小职责

preflight 的最小职责是：

1. 根据 `final_mapping` 推导相关 `backup_dir`
2. 对每个相关 `backup_dir` 执行最小可执行性检查
3. 产出统一 manifest 供 orchestrator 消费

最小可执行性检查至少包括：

- `backup_dir` 存在
- `backupinfo.json` 存在且可读
- `backupinfo.json` 中存在可用 `tree`

更高成本的完整性检查或冲突检查，可以作为扩展位存在，但不属于本轮最小契约。

## 六、manifest 契约

manifest 至少包含以下稳定字段：

- `ok`
- `backup_dirs`
- `errors`
- `warnings`
- `timestamp`

其中 `backup_dirs` 的每个条目至少应包含：

- `path`
- `gate_pass`
- `gate_errors`
- `applicable_entries`

manifest 的重点是“可被 orchestrator 与前端稳定消费”，而不是预先绑定所有未来诊断字段。

## 七、与 orchestrator 的关系

`dispatch()` 路由到文件操作管线时，Planner 层内调 preflight，orchestrator 按如下流程执行：

```text
dispatch(request)
  -> Select Resolver / Resolve → CleanContext
  -> Planner: plan_fileops() → FileOpsPlan (含 preflight manifest)
  -> Preflight gate check: manifest.ok?
  -> ok=true → execute primitive (apply / restore / backup)
  -> ok=false → return preflight result, skip primitive
```

注意：REST API 不直接暴露 preflight 接口；preflight 的执行与缓存由 orchestrator 管理，API 路由
只触发 `dispatch()` 入口，不直接调用或绕过 preflight。

调用关系由 `DESIGN_ORCHESTRATOR.md` 记录，本文档只冻结 preflight 子模块本身。

## 八、cache policy

### 8.1 当前默认策略

- preflight 结果允许被缓存。
- 当前默认只要求“可缓存”，不要求“必须持久化缓存”。
- 进程内或工作区会话级复用属于允许范围。

### 8.2 持久缓存的前置条件

若未来要引入持久缓存，必须先冻结：

- cache key
- 失效规则
- 存储归属

在这些前提缺失前，不得把 manifest 或 cache 提升为新的权威输入。

## 九、明确不做什么

preflight 不负责以下事项：

- 不执行 apply 文件操作
- 不定义 apply 的返回结构
- 不把 cache 升格为权威数据源
- 不替代 engine / schema 对输入合法性的约束

## 十、当前实现涉及的主要错误码与警告码

preflight 主要复用以下条目：

- `E_BACKUP_DIR_MISSING`
- `E_BACKUP_INFO_MISSING`
- `E_BACKUP_TREE_MISSING`
- `W_BACKUP_GATE_FAILED`

统一解释与默认严重级别，以 `TERMS_ERROR_CODES.md` 为准。

## 十一、测试组可据此断言的“应该是什么样”

测试组可以据本文档编写正例断言：

- preflight 独立于 apply 原语——preflight 不调用 apply，不执行文件替换，不改动磁盘
- manifest 必须包含 ok、backup_dirs、errors、warnings、timestamp
- backup_dirs 每个条目必须包含 path、gate_pass、gate_errors、applicable_entries
- apply preflight：backup_dir 不存在 → gate_pass=false，记录 E_BACKUP_DIR_MISSING
- apply preflight：backupinfo.json 不存在 → gate_pass=false，记录 E_BACKUP_INFO_MISSING
- apply preflight：backupinfo.json 存在但 tree 缺失 → gate_pass=false
- restore preflight：backup_dir 不存在 → manifest.ok=false，记录 E_BACKUP_DIR_MISSING
- restore preflight：backup_dir 存在 → gate_pass=true，gate_errors=[]
- 空 backup_dirs 时 trivially pass（ok=true，backup_dirs=[]）
- manifest 失败时 orchestrator 不调用 apply
- cache 只是优化层，不改变决策语义
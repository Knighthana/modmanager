# DESIGN_RESTORE_OPS — Restore 执行设计

> Status: active
> Last update: 2026-05-21 — restore_ops.py as independent module
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 restore 如何消费当前 mapping、backupinfo 与 backup_dir 执行恢复，不承担上层流程门禁职责
> Supersedes: DESIGN_BACKUP.md

## 一、职责边界

实现文件：`src/modmanager/restore_ops.py`（独立原语模块）。

本文档只描述 restore 如何执行。

本文档不负责定义：

- backup_dir 应该长什么样
- backupinfo 应该长什么样
- 如何执行 backup
- 是否要求用户在产品流程上先做 backup

这些问题分别由 `DESIGN_BACKUP_DIR.md`、`DESIGN_BACKUP_OPS.md` 与上层产品流程决定。

## 二、总原则

### 2.1 restore 是执行原语，只干活

- restore 不负责检查更高层状态。
- restore 不负责判断用户是否“应该先 backup”。
- restore 不承担上层流程门禁职责。

restore 只消费当前可见输入并执行恢复：

- 当前 mapping
- 对应 backup_dir
- 该 backup_dir 根目录中的 `backupinfo.json`

### 2.2 mapping 只决定 scope，backupinfo 只决定 truth

- 当前 mapping 只用于判定这次 restore 里哪些文件“被命中过”。
- `backupinfo.json` 只用于提供这些已备份实体“应该是什么样”的结构与 hash 权威。
- 二者职责不可混用。

换言之：

- mapping 决定 restore scope
- backupinfo 决定 restore truth

### 2.3 切换 mapping 后再 restore 是设计内功能

- restore 与 backup 解耦。
- 切换到另一份当前生效的 mapping 后再执行 restore，属于设计内允许的行为。
- restore 不关心这份 mapping 是否与创建 backup 时的 mapping 相同；它只关心当前命中集合，以及 backup_dir 中是否存在可恢复实体。

## 三、执行输入

### 3.1 当前 mapping

restore 消费当前 mapping，用于从目标路径集合中确定本次 restore 的命中集合。

对每个候选文件而言，只有两种状态：

- 命中：参与本次 restore
- 未命中：不参与本次 restore

### 3.2 backup_dir

- restore 从 `build_backup_dirs()` 或等效机制定位对应的 `backup_dir`。
- `backup_dir` 提供实际可复制回目标位置的文件实体。

### 3.3 backupinfo

- restore 读取 `backup_dir/backupinfo.json`。
- `backupinfo.json` 的结构与节点定义由 `DESIGN_BACKUP_DIR.md` 规定。
- restore 使用其中的 `tree`、`hashtype`、`hashvalue` 进行结构与 hash 对照。

## 四、执行语义

### 4.1 命中集行为

- 命中=true：该文件参与本次 restore，按 backup_dir 和 backupinfo 执行恢复。
- 命中=false：该文件与本次 restore 无关，不处理。

### 4.2 hash 行为

- 默认模式下，也就是 `force=false` 时，restore 可以对目标文件与 backup 实体做 hash 比对。
- 若目标文件与 backup 文件 hash 一致，可跳过实际复制。
- `force=true` 时，应直接跳过 hash 计算并执行文件操作，而不是先计算 hash 再决定是否跳过。
- `force` 只改变执行策略，不改变 backupinfo 的权威地位。

### 4.3 文件恢复行为

- restore 按命中集合找到目标路径。
- 对于可恢复的目标，从 `backup_dir` 中取对应实体文件复制回目标位置。
- 若父目录不存在，restore 可创建所需父目录后再复制。

## 五、warning 与 error 的边界

restore 不做上层门禁判断，但会在执行过程中产生 warning 或 error。

### 5.1 warning

以下情况原则上记为 warning：

- 某目标在当前 restore scope 内，但在对应 `backup_dir` 中找不到可恢复实体
- 某个 backup_dir 无法通过可恢复性检查，因此该目录下目标整体跳过
- 存在本次 restore 未命中的外部文件或孤儿文件，需要提示但不阻断其它恢复

### 5.2 error

以下情况原则上记为 error：

- 复制回目标位置时发生不可恢复的 I/O 失败
- 当前 restore 动作无法继续执行该条目
- 已进入执行阶段但关键输入损坏到无法继续工作

具体错误码与默认严重级别以 `TERMS_ERROR_CODES.md` 为准。

## 六、当前实现应遵循的最小流程

```text
读取当前 mapping
  -> 定位本次命中集合
  -> 推导对应 backup_dir
  -> 读取 backup_dir/backupinfo.json
  -> 若 force=false，则对命中条目执行 hash 对照
  -> 若 hash 一致，则 skip
  -> 若 force=true，则直接跳过 hash 计算
  -> 需恢复则从 backup_dir 复制回目标位置
  -> 找不到可恢复实体则 warning
  -> 确实执行失败则 error
```

## 七、测试组可据此断言的“应该是什么样”

测试组可以直接据此编写正例断言：

- restore 只处理当前 mapping 命中的文件
- 未命中的文件不参与本次 restore
- restore 依赖 `backup_dir` 与 `backupinfo.json` 执行，不负责上层门禁判断
- `force=true` 时直接跳过 hash 计算并执行文件操作，不改变 backupinfo 的 truth 地位
- 找不到可恢复实体时应产生 warning，而不是隐式成功
- 不可继续执行的复制失败应产生 error
- restore 相关错误码与警告码统一以 `TERMS_ERROR_CODES.md` 为准

反例、异常构造和产品层“是否允许点击 restore”的策略，不属于本文档职责。
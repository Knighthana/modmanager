# DESIGN_BACKUP_OPS — Backup 执行设计

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义如何执行 backup，包括创建 backup_dir、写入 backupinfo、扫描与差异备份，但不重复定义 backup_dir 结构本身
> Supersedes: DESIGN_BACKUP.md

## 一、职责边界

本文档只描述如何进行 backup。

本文档不负责定义：

- `backup_dir` 应该长什么样
- `backupinfo.json` 的结构应该长什么样
- restore 如何执行

这些内容分别由 `DESIGN_BACKUP_DIR.md` 和 `DESIGN_RESTORE_OPS.md` 负责。

## 二、总原则

### 2.1 backup 负责产出可恢复输入

- backup 的目标不是维护状态机，而是产出可供 restore 消费的执行输入。
- 这些输入包括：
  - 完整的 `backup_dir`
  - `backup_dir` 根目录中的 `backupinfo.json`
  - 可用于恢复的实体文件集合

### 2.2 backup_dir 结构以 DESIGN_BACKUP_DIR 为准

- backup 负责创建与写入 `backup_dir`。
- 但 `backup_dir` 与 `backupinfo.json` 的结构定义，不在本文档内重复描述。
- 所有结构、字段、节点语义，统一以 `DESIGN_BACKUP_DIR.md` 为准。

### 2.3 backup 是懒备份，不承担未来产品限制

- 当前 backup 设计允许按需、按命中目标执行懒备份。
- 更高层是否要求“先 backup 才允许其它操作”，不属于 backup 语义本身。

## 三、执行输入

backup 执行至少需要：

- 当前 `final_mapping`
- `database`
- `user_config`

其中：

- `final_mapping` 用于确定哪些目标需要备份
- `database` 用于推导每个目标归属哪个 app / contentid / steam 库
- `user_config` 用于读取 `baksuffix`、`bakignore` 等配置

## 四、backup 的最小流程

```text
读取 final_mapping / database / user_config
  -> 推导每个目标对应的 backup_dir
  -> 创建 backup_dir
  -> 初始化 backupinfo.json
  -> 复制命中目标到 backup_dir
  -> 扫描 backup_dir 生成完整 tree
  -> 写回最终 backupinfo.json
```

## 五、backup_dir 的创建与初始化

### 5.1 backup_dir 推导

- backup 首先调用 `build_backup_dirs()` 或等效逻辑，推导出 `{backup_dir: [file_paths]}`。
- backup_dir 的命名、路径位置、时间戳来源、多库行为，不在本文档中展开，统一引用 `DESIGN_BACKUP_DIR.md` 与对应 builder 设计。

### 5.2 backupinfo 初始化

- 在正式复制文件前，backup 应在 `backup_dir` 根目录写入初始 `backupinfo.json`。
- 初始化写入的目标是占位与建立文件位置，不是宣告结构完成。
- 最终 `tree` 与时间字段应在复制完成并扫描后回写为完成态。

## 六、差异备份行为

### 6.1 备份对象

- backup 只处理当前 `final_mapping` 命中的目标文件。
- 文件写入 backup_dir 时，以源根目录相对路径落盘。

### 6.2 dry_run 行为

- `dry_run=true` 时，backup 只返回“将会备份什么”，不真正复制文件。
- 返回记录中的路径应满足路径结尾约束：目录语义统一走 `dir`，文件路径不得带多余尾 `/`。

### 6.3 正式执行行为

- 正式执行时，将目标文件复制进对应 `backup_dir`。
- 某个条目复制失败时，记录 error，不得静默吞掉。

## 七、循环防护与忽略规则

### 7.1 三层忽略规则

backup 扫描与复制时适用以下忽略层：

| 层 | 来源 | 粒度 | 说明 |
|----|------|------|------|
| 硬编码底线 | `.kmmbackup` | 目录后缀 | 始终生效 |
| 用户配置 | `user_config.bakignore` | 后缀 / 模式 | 用户附加忽略 |
| 文件规则 | `.kmmbakignore` | gitignore 模式 | 文件级忽略 |

### 7.2 .kmmbakignore 文件本身

- `.kmmbakignore` 本身属于应被保留的规则文件。
- backup 时，各级 `.kmmbakignore` 文件应被复制进对应 `backup_dir`。
- `backupinfo.json` 不属于源规则文件，不参与这套复制语义。

## 八、backupinfo 的生成与回写

### 8.1 生成时机

- 复制完成后，backup 应扫描 `backup_dir` 的实际内容。
- 基于扫描结果生成完整的 `tree`。

### 8.2 回写字段

回写的 `backupinfo.json` 至少应包含：

- `snapshot_time`
- `last_modified_time`
- `schema_version`
- `tree`

字段定义与结构约束见 `DESIGN_BACKUP_DIR.md`。

## 九、脏状态与冲突检查

backup 相关实现可以暴露以下检查能力：

- 检测 metadata 缺失或 tree 缺失的脏状态
- 检测 backup_dir 内实际实体与 `backupinfo.json` 的冲突
- 检测目标文件与 backup 副本的漂移

这些检查的错误码与默认严重级别统一以 `TERMS_ERROR_CODES.md` 为准。

## 十、当前实现涉及的主要错误码与警告码

backup 及 backup_dir 相关设计至少涉及以下条目：

- `E_BACKUP_STATE_UNSTABLE`
- `W_BACKUP_CONTENTID_SKIPPED`
- `W_BACKUP_VERSION_LAGGED`
- `E_BACKUP_COPY_FAILED`
- `E_BACKUP_DIRTY_STATE`
- `E_TREE_CONFLICT`
- `E_ENTITY_CONFLICT`

最终解释与默认严重级别统一以 `TERMS_ERROR_CODES.md` 为准。

## 十一、测试组可据此断言的“应该是什么样”

测试组可以据本文档编写正例断言：

- backup 会先推导 `backup_dir`，再执行复制
- backup 会在 `backup_dir` 根目录生成 `backupinfo.json`
- backup 完成后会回写完整 `tree`
- `.kmmbakignore` 应被复制进 backup_dir，对应规则可被保留
- 条目复制失败会产生 error，而不是静默成功

反例、异常注入与产品层操作限制，不属于本文档职责。
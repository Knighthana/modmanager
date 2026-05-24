# DESIGN_BACKUP_OPS — Backup 执行设计

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义如何执行 backup。backupinfo.json 的结构定义见 DESIGN_BACKUP_DIR.md
> Supersedes: DESIGN_BACKUP.md
> Last update: 2026-05-21 — 重新规定建树时机（先建树后备份）、树节点状态机、ignore 缓存

## 一、职责边界

本文档只描述 backup 原语本身。

本文档不负责定义：
- `backup_dir` 的目录结构
- `backupinfo.json` 的 schema 结构
- restore 如何执行

前置门禁（preflight / gate check）为 Planner 层职责：`plan_fileops()` 在 Planner 层调用 preflight，orchestrator 的 `dispatch()` 据此决策是否继续执行。backup 自身流程中不承担 gate 判定逻辑。

## 二、总原则

### 2.1 backup 负责产出可恢复输入

- backup 的目标是在backup dir下提供懒的增量备份。
- 这些输入包括：完整的 `backup_dir`、`backup_dir` 根目录中的 `backupinfo.json`、可用于恢复的实体文件集合。

### 2.2 backup_dir 结构以 DESIGN_BACKUP_DIR 为准

- backup 负责创建与写入 `backup_dir`。但结构定义统一以 `DESIGN_BACKUP_DIR.md` 为准。

### 2.3 backup 是懒备份

- 当前 backup 设计只备份 `final_mapping` 命中的文件，不主动扫描未命中内容。

## 三、执行输入

backup 执行至少需要：

- 当前 `final_mapping`
- `database`
- `user_config`

其中：
- `final_mapping` 用于确定哪些目标需要备份
- `database` 用于推导每个目标归属哪个 app / contentid / steam 库
- `user_config` 用于读取 `baksuffix` 等配置

## 四、Ignore 规则缓存

ignore 的计算非常常用。Planner 在 `plan_fileops()` 阶段计算出的 ignore 结果必须以某种形式缓存并提供给 backup 和 restore 原语直接消费，不允许 backup 或 restore 原语重新计算 ignore 规则。

缓存形式是：
- Planner 直接将 `IgnoreRuleSet` 对象放入 `FileOpsPlan`，backup 原语从 plan 中取用

## 五、backup_dir 的推导与创建

### 5.1 backup_dir 推导

backup 首先计算当前的 backup_dir 字符串应该是什么（通过 `build_backup_dirs()` 或等效逻辑）。backup_dir 的命名、路径位置、时间戳来源、多库行为统一引用 `DESIGN_BACKUP_DIR.md` 与对应 builder 设计。

### 5.2 backup_dir 创建与建树

当被 backup 的目录中没有 backup_dir 的时候，建立这个 backup_dir 目录，在这个目录的根位置创建 `backupinfo.json` 并且立刻开始建树操作。

**建树**：在 ignore 的基础上，迭代扫描源 `mixed_id`（base 或者 mod）目录中**所有**的目录和文件放入树上的相应结点。所有文件的 hash 对象的 `hashtype` 标记为 `"invalid"`，`hashvalue` 标记为 `"0"`。

建树完成后，进入正常的 backup 工作。

## 六、backup 执行流程

将整个树读入内存，同时开始进行文件操作。

1. 根据 mapping 所确定的 scope（被命中的文件），在 ignore 的基础上，进行 backup 操作。

2. 每备份一个文件前，先看树上是否有对应的结点。如果树上没有这个结点，**不允许**改树，而应该记录一条「某文件不属于这个目录，故跳过」的详细含有该文件 path 的警告。

3. 每备份一个文件前，先看这个文件是否已经备份过。若其 `"isbackuped"` 为 `true`，则跳过。

4. 若 `"isbackuped"` 为 `false`，根据当前的设定，填入树上对应文件结点的 `hashtype` 为设定的值。在当前版本下，这个值为 `"sha256"`。再计算这个文件在这种 type 下的 `hashvalue` 值。

5. 进行备份操作，也即将要被备份的文件从源目录的对应位置，复制到 backup_dir 中的「对应」位置。

6. 更新 tree 上该文件的 `"isbackuped"` 为 `true`。

### 树节点状态的不可逆约束

tree 创建之后 node 的结构本身为 const，不允许新增或删除结点。FileNode 的字段变更遵循以下不可逆规则：

- `isbackuped` 只能从 `false` 变成 `true`，不能反向
- `hashtype` 只能从 `"invalid"` 变成有意义的值（如 `"sha256"`），不能反向
- `hashvalue` 只能从 `"0"` 变成有意义的 hash hex string，不能反向
- **只有文件拷贝完成之后**，才能将 `"isbackuped"` 转变为 `true`。如果拷贝过程被异常打断，那么不允许提前修改 `isbackuped` 的值

这些约束是 `DESIGN_BACKUP_DIR.md` 中树节点 schema 的运行时强制规则。

## 七、tree 的生命周期与只读约束

### 7.1 首次备份——建树

当 backup_dir 不存在时：创建 backup_dir → 创建 `backupinfo.json` → 立即建树（扫描源目录，所有文件标记 `isbackuped=false`，hash `hashtype="invalid"` `hashvalue="0"`）→ 写入 `backupinfo.json` → 然后按 §六 执行备份操作。

### 7.2 后续备份——不重建树

当 backup_dir 已存在且 `backupinfo.json` 中的 tree 已完成（存在且非空，非 `{}` 占位符）时：将现有 tree 读入内存，直接按 §六 执行备份操作。**不再扫描源目录重建 tree。**

tree 在首次建树之后结构为 const——不新增结点、不删除结点。后续备份只修改已有结点的 `isbackuped` / `hashtype` / `hashvalue` 字段。

### 7.3 tree 不完整时的处理

当 backup_dir 存在但 tree 为空（`{}` 占位符）或不完整时：视为首次备份，重新执行 §五.2 的建树操作。

## 八、差异备份行为

### 8.1 备份对象

backup 只处理当前 `final_mapping` 命中的目标文件。文件写入 backup_dir 时，以源根目录相对路径落盘。

### 8.2 dry_run 行为

`dry_run=true` 时，backup 只返回「将会备份什么」，不真正复制文件，不修改 tree。返回记录中的路径应满足路径结尾约束。

### 8.3 正式执行行为

正式执行时，将目标文件复制进对应 `backup_dir`。某个条目复制失败时记录 error，不得静默吞掉。**只有复制成功后才更新 tree 中对应结点的状态**。

## 九、循环防护与忽略规则

忽略规则由 Orchestrator Planner 层统一管理，对所有操作（backup / apply / restore）生效。完整规范见 `DESIGN_KMMIGNORE_RULES.md`。

backup 原语自身不处理忽略——由 Planner 在构建 `FileOpsPlan` 时过滤。Planner 计算结果以 `IgnoreRuleSet` 对象形式缓存在 `FileOpsPlan` 中，backup 原语直接取用。

`backupinfo.json` 的 tree 扫描同样应用 IgnoreRuleSet，确保被忽略文件不进入 tree。

## 十、backupinfo 的生成与回写

### 10.1 生成时机

- **首次备份**（backup_dir 不存在或 tree 为空）：建树操作在文件复制之前执行。扫描源目录（`backup_dir` 的父目录，即 content_root）生成完整文件结构镜像，写入 `backupinfo.json`。
- **后续备份**（tree 已存在且完整）：不重建树。将现有树读入内存，按 §六 逐个更新结点状态，每次更新后写回 `backupinfo.json`。

### 10.2 回写字段

回写的 `backupinfo.json` 应包含：

- `schema_namespace`
- `tree_created_time`
- `last_modified_time`
- `schema_version`
- `tree`

字段定义与结构约束见 `DESIGN_BACKUP_DIR.md`。

## 十一、脏状态与冲突检查

backup 相关实现可以暴露以下检查能力：

- 检测 metadata 缺失或 tree 缺失的脏状态
- 检测 backup_dir 内实际实体与 `backupinfo.json` 的冲突
- 检测目标文件与 backup 副本的漂移

这些检查可作为 preflight 的输入；orchestrator 负责综合这些输出并做出 gate 判定，backup 本身不负责门禁决策。

## 十二、错误码与警告码

backup 至少涉及以下条目：

- `E_BACKUP_STATE_UNSTABLE`
- `W_BACKUP_CONTENTID_SKIPPED`
- `W_BACKUP_VERSION_LAGGED`
- `E_BACKUP_COPY_FAILED`
- `E_BACKUP_DIRTY_STATE`
- `E_TREE_CONFLICT`
- `E_ENTITY_CONFLICT`
- `W_BACKUP_NODE_NOT_IN_TREE`：树上没有对应结点，跳过该文件

最终解释与默认严重级别以 `TERMS_ERROR_CODES.md` 为准。

## 十三、测试断言

测试组可以据本文档编写正例断言：

- 首次 backup 时：backup_dir 不存在 → 创建 backup_dir → 建树（所有文件 `isbackuped=false`，hash `hashtype="invalid"` `hashvalue="0"`）→ 执行备份 → 更新树中对应结点的 `isbackuped` / `hashtype` / `hashvalue`
- 后续 backup 时：backup_dir 已存在且 tree 完整 → 不重建树 → 只更新已有结点的状态
- 树上没有对应结点时：记录 `W_BACKUP_NODE_NOT_IN_TREE` 警告，跳过该文件
- `isbackuped` 不能从 `true` 变回 `false`；`hashtype` 不能从 `"sha256"` 变回 `"invalid"`；`hashvalue` 不能从有效 hex 变回 `"0"`
- 文件拷贝失败时：`isbackuped` 保持 `false`，不被提前修改
- 条目复制失败会产生 error，而不是静默成功

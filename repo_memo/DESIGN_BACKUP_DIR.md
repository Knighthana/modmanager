# DESIGN_BACKUP_DIR — Backup Dir 与 BackupInfo 结构设计

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 定义 backup_dir 应该是什么样，以及 backupinfo 作为 backup_dir 成员时的结构、字段与权威边界
> Supersedes: DESIGN_BACKUP.md

## 一、职责边界

本文档只回答两类问题：

- `backup_dir` 目录应该是什么样
- `backupinfo.json` 应该是什么样

本文档不负责定义：

- 如何执行备份
- 如何执行恢复
- 如何做上层流程门禁

这些内容分别由 `DESIGN_BACKUP_OPS.md`、`DESIGN_RESTORE_OPS.md` 负责。

## 二、总原则

### 2.1 backupinfo 是 backup_dir 内的权威快照

- `backupinfo.json` 属于 `backup_dir` 的成员，不是工作区成员。
- `backupinfo.json` 是该 `backup_dir` 内文件内容、目录结构与 hash 元数据的唯一权威快照。
- 任何恢复动作若需要判断某个已备份实体“应该是什么样”，只能以该 `backup_dir` 内的 `backupinfo.json` 为准。

### 2.2 backup_dir 是内容容器，backupinfo 是结构说明

- `backup_dir` 保存可被恢复的实际文件内容。
- `backupinfo.json` 保存这些内容对应的冻结结构与 hash 元数据。
- 二者共同组成 restore 的执行输入之一，但职责不同：
  - `backup_dir` 提供可搬运的实体文件
  - `backupinfo.json` 提供这些实体的权威说明

### 2.3 目录语义统一使用 dir

- 在 backupinfo 语义中，所有表示目录含义的键、字段、节点类型、术语，一律使用 `dir`。

### 2.4 结构冻结，非局部变更必须先改 schema 和文档

- `backupinfo.json` 的结构是冻结契约，不允许实现端自行扩展临时字段。
- 若需变更字段、节点结构或节点类型，必须先更新 `repo_spec/backupinfo.schema.json` 与相关冻结文档，再改代码。

## 三、backup_dir 的目录形态

### 3.1 最小目录形态

每个 `backup_dir` 至少包含：

- `backupinfo.json`
- 一个或多个被备份的文件实体

示意：

```text
<backup_dir>/
  backupinfo.json
  some/file/a.ext
  some/file/b.ext
```

### 3.2 backupinfo.json 的位置

- `backupinfo.json` 固定放在 `backup_dir` 根目录。
- `backupinfo.json` 不属于被备份源文件集合本身，因此不进入 `tree` 的递归内容。

### 3.3 tree 的根节点语义

- `tree` 的根节点表示对应源目录（content_root）的完整文件结构镜像，而非 backup_dir 本身的快照
- 根节点类型必须为 `dir`。
- 根节点的 `name` 为源目录名（即 content_root 的最后一段）

## 四、backupinfo.json 的根结构

### 4.1 根字段

`backupinfo.json` 根对象必须且只允许包含以下字段：

| 字段 | 类型 | 含义 |
|------|------|------|
| `schema_namespace` | `string` | Schema 命名空间标识，固定为 `"KMM_BackupInfo"` |
| `snapshot_time` | `string` | 快照创建时间，ISO8601 date-time |
| `last_modified_time` | `string` | 最后一次被本项目工具写入的时间，ISO8601 date-time |
| `schema_version` | `string` | 当前 backupinfo schema 版本 |
| `tree` | `DirNode` | 全量快照树 |

补充约束：

- 根对象 `additionalProperties=false`
- 五个字段缺一不可

### 4.2 根字段语义

- `snapshot_time`：表示这份快照首次生成时刻。
- `last_modified_time`：表示本项目工具最后一次写入该 `backupinfo.json` 的时刻。
- `schema_version`：用于标识此文件遵循的结构版本。
- `tree`：该 backup 对应源目录的全量冻结文件结构镜像。每个文件标记 isbackuped 以区分是否已有备份副本

## 五、tree 的递归节点结构

### 5.1 DirNode

目录节点必须满足：

| 字段 | 类型 | 约束 |
|------|------|------|
| `name` | `string` | 当前目录名 |
| `type` | `string` | 固定为 `dir` |
| `children` | `array` | 子节点列表，元素为 `DirNode` 或 `FileNode` |

约束：

- `DirNode` 不允许出现 `isbackuped`、`hashtype`、`hashvalue`
- `DirNode` 不允许额外字段

### 5.2 FileNode

文件节点必须满足：

| 字段 | 类型 | 约束 |
|------|------|------|
| `name` | `string` | 当前文件名 |
| `type` | `string` | 固定为 `file` |
| `isbackuped` | `boolean` | 是否已完成备份 |
| `hashtype` | `string` | 当前 hash 算法类型 |
| `hashvalue` | `string` | 当前 hash 值 |

约束：

- `FileNode` 不允许出现 `children`
- `FileNode` 不允许额外字段

### 5.3 递归关系

- `tree` 根节点必须是 `DirNode`
- `DirNode.children[]` 只能包含 `DirNode` 或 `FileNode`
- `FileNode` 为叶子节点，不可再有子节点

### 5.4 tree 的生成规则

`tree` 是**源目录的完整结构镜像**，而非 `backup_dir` 的快照。

1. **扫描对象**：以源根目录（`backup_dir` 的父目录，即 `content_root`）为根，递归遍历。
2. **节点标记**：遍历到的每个文件，检查其在 `backup_dir` 中是否有对应副本：
   - 有副本 → `isbackuped: true`，`hashtype` / `hashvalue` 取自备份副本
   - 无副本 → `isbackuped: false`，`hashtype` / `hashvalue` 为占位值（`"sha256"` / `""` 或 `"0"`）
3. **排除规则**（三层忽略，由 Orchestrator Planner 层在 `plan_fileops()` 中统一收集后传入）：
   - 硬编码底线：`.kmmbackup` 后缀目录始终排除
   - 用户配置：`user_config.bakignore` 中的后缀 / 模式
   - 文件规则：源目录各级 `.kmmbakignore` 文件（gitignore 语法）
   - `backupinfo.json` 自身不进入 tree 递归

## 六、backupinfo 与 schema 的关系

- `repo_spec/backupinfo.schema.json` 是 backupinfo 结构校验的 schema 权威来源。
- 本文档负责解释“应该是什么样”，schema 负责给出机器可校验的结构约束。
- 二者冲突时，应先修正文档或 schema，使二者重新一致；实现不得自行择一。

## 七、restore 可依赖的 backup_dir 事实

尽管 restore 语义由 `DESIGN_RESTORE_OPS.md` 定义，但 restore 可以依赖本文档中的以下事实：

- `backupinfo.json` 固定存在于 `backup_dir` 根目录
- `backupinfo.json` 是结构与 hash 元数据的唯一权威
- `tree` 是冻结的全量快照树
- 目录语义统一使用 `dir`
- 文件节点的 hash 信息位于 `FileNode.hashtype` 与 `FileNode.hashvalue`

## 八、测试组可据此断言的“应该是什么样”

测试组可以直接基于本文档编写正例断言：

- `backup_dir` 根目录应包含 `backupinfo.json`
- `backupinfo.json` 根字段必须为 `schema_namespace`、`snapshot_time`、`last_modified_time`、`schema_version`、`tree`
- `tree` 根节点必须是 `dir`
- 目录节点只能是 `dir`，文件节点只能是 `file`
- `FileNode` 必须带 `isbackuped`、`hashtype`、`hashvalue`

反例、异常构造与违规输入枚举，不属于本文档职责。
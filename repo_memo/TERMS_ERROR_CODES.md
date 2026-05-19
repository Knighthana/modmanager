# Error Codes Freeze

> Status: active
> Authority: authoritative
> Read-Tier: always
> Purpose: 统一记录 backupinfo、backup、restore 相关错误码与默认严重级别，供后端、前端、测试与后续 i18n 共用

## 一、用途与边界

- 本文档是错误码与警告码的统一入口。
- 任何新引入的 backupinfo、backup、restore 相关 `E_` / `W_` 码，都应先或同步登记到这里。
- 前缀 `E_` / `W_` 不是唯一严重级别来源；默认严重级别以本表 `default_severity` 为准。

## 二、固定表结构

| code | phase | trigger | default_severity | summary | notes |
|------|-------|---------|------------------|---------|-------|
| `E_BACKUP_STATE_UNSTABLE` | `backup-dir` | 无法读取 appmanifest，或 StateFlags / buildid 不满足稳定性要求 | `error` | backup_id 无法稳定生成 | appid 相关；拒绝将该实体纳入可用 backup_dir |
| `W_BACKUP_CONTENTID_SKIPPED` | `backup-dir` | contentid 的 ACF 缺失、字段缺失或字段非法 | `warning` | 该 contentid 被跳过 | 不阻断其它 contentid |
| `W_BACKUP_VERSION_LAGGED` | `backup-dir` | `T_local < T_remote` | `warning` | 本地 workshop 版本滞后 | 等待 Steam 更新后再备份 |
| `E_BACKUP_DIR_MISSING` | `backupinfo` | 对应 backup_dir 不存在 | `error` | backup_dir 缺失 | 可恢复性检查失败 |
| `E_BACKUP_INFO_MISSING` | `backupinfo` | `backupinfo.json` 缺失或不可读 | `error` | backupinfo 缺失 | 无法获得结构权威 |
| `E_BACKUP_TREE_MISSING` | `backupinfo` | `backupinfo.json` 中缺少 `tree` | `error` | 快照树缺失 | 结构不完整 |
| `E_BACKUP_DIRTY_STATE` | `backupinfo` | metadata 缺失或 tree 缺失，目录处于不完整状态 | `error` | backup_dir 处于脏状态 | 说明备份曾被中断或写入不完整 |
| `E_TREE_CONFLICT` | `backupinfo` | `tree` 非法或与预期结构不一致 | `error` | 快照树冲突 | 结构层冲突 |
| `E_ENTITY_CONFLICT` | `backupinfo` | backup_dir 中文件缺失或 hash 与 tree 记录不一致 | `error` | 备份实体冲突 | 实体层冲突 |
| `E_TREE_CONFLICT_TARGET_DRIFT` | `restore` | 目标文件与 backup 副本产生漂移 | `error` | 目标文件漂移 | 面向冲突检查，而非普通 restore 成功路径 |
| `W_BACKUP_GATE_FAILED` | `restore` | 对应 backup_dir 无法通过可恢复性检查 | `warning` | 该 backup_dir 在本次 restore 中被整体跳过 | restore 继续处理其它目录 |
| `E_RESTORE_COPY_FAILED` | `restore` | 从 backup_dir 复制回目标位置失败 | `error` | 恢复复制失败 | 当前条目执行失败 |
| `E_EXTERNAL_FILE_ORPHAN` | `restore` | 检测到本次 restore 未命中的外部文件或孤儿文件 | `warning` | 外部孤儿文件提示 | 当前实现虽然以 `E_` 前缀输出，但默认严重级别按 warning 处理 |
| `E_BACKUP_COPY_FAILED` | `backup` | 将目标文件复制进 backup_dir 失败 | `error` | 备份复制失败 | 当前条目未成功写入 backup |

## 三、使用约束

- 设计文档描述 warning / error 时，应引用本文档，而不是各自重复定义严重级别。
- 前端聚合展示、筛选、分组、i18n 映射时，应以本文档字段为准。
- 测试组校对错误码含义时，应以本文档为准，而不是反向阅读代码猜测。# Error Code Terms

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 统一记录项目内错误码与警告码的语义、触发阶段与默认严重级别，供后端、前端、测试与后续 i18n 共用

## 一、用途

本文档是错误码与警告码的统一术语入口。

主要目的：

- 降低非相关模块开发小组查找定义的成本
- 避免不同模块对同一错误码产生不同解释
- 为前端归拢、筛选、展示与 i18n 提供稳定来源
- 为测试组提供“应该出现什么码”的规范依据

## 二、表结构

所有错误码条目至少包含以下列：

| 字段 | 含义 |
|------|------|
| `code` | 错误码或警告码本体 |
| `phase` | 发生阶段，例如 `backup_dir` / `backup` / `restore` |
| `trigger` | 触发条件 |
| `default_severity` | 默认严重级别，当前使用 `error` / `warning` |
| `summary` | 面向开发与测试的简要说明 |
| `notes` | 额外补充说明、边界或实现备注 |

## 三、当前 backupinfo / backup / restore 相关条目

| code | phase | trigger | default_severity | summary | notes |
|------|-------|---------|------------------|---------|-------|
| `E_BACKUP_STATE_UNSTABLE` | `backup_dir` | appmanifest 不可读、StateFlags 非允许值、buildid 缺失或非法 | `error` | 游戏本体无法产出稳定 backup_id | 归属 backup_dir 推导阶段 |
| `W_BACKUP_CONTENTID_SKIPPED` | `backup_dir` | appworkshop 缺失、时间戳缺失、时间戳非法 | `warning` | 某个 contentid 因输入不完整被跳过 | restore 不直接产出该码 |
| `W_BACKUP_VERSION_LAGGED` | `backup_dir` | `T_local < T_remote` | `warning` | contentid 版本滞后，当前不应生成稳定 backup_id | 旧文档若出现 error 口径，以此文档为准 |
| `E_BACKUP_DIR_MISSING` | `restore` | 目标 backup_dir 不存在 | `error` | 备份目录缺失 | 常见于 gate 检查 |
| `E_BACKUP_INFO_MISSING` | `restore` | `backupinfo.json` 缺失或不可读 | `error` | backupinfo 缺失 | 当前实现经 gate 返回 |
| `E_BACKUP_TREE_MISSING` | `restore` | `backupinfo.json` 中缺少 `tree` | `error` | backupinfo 缺少权威快照树 | 当前实现经 gate 返回 |
| `E_BACKUP_DIRTY_STATE` | `backup` | backup_dir 中存在部分文件但 metadata/tree 缺失 | `error` | 备份目录处于脏状态 | 用于脏状态检测 |
| `E_TREE_CONFLICT` | `restore` | `tree` 非法或不可用于比对 | `error` | 权威树结构冲突 | 用于冲突检查 |
| `E_ENTITY_CONFLICT` | `restore` | 备份实体缺失或 hash 不匹配 | `error` | 某个实体与 backupinfo 描述不一致 | 用于冲突检查 |
| `E_TREE_CONFLICT_TARGET_DRIFT` | `restore` | 目标文件与备份文件发生漂移 | `error` | 目标实体与备份实体不一致 | 用于冲突检查 |
| `W_BACKUP_GATE_FAILED` | `restore` | gate 检查失败导致某个 backup_dir 被整组跳过 | `warning` | 当前 backup_dir 未进入 restore 执行 | warning，不阻断其它 backup_dir |
| `E_RESTORE_COPY_FAILED` | `restore` | 从 backup_dir 复制回原路径时发生 I/O 失败 | `error` | 某个命中文件恢复失败 | restore 主流程直接产出 |
| `E_EXTERNAL_FILE_ORPHAN` | `restore` | 发现 backup 外的孤儿文件 | `warning` | 存在未被当前 restore 集合覆盖的外部文件 | 当前实现前缀虽为 E_，严重级别按 warning 解释 |
| `E_BACKUP_COPY_FAILED` | `backup` | 备份复制阶段发生 I/O 失败 | `error` | 某个文件未能写入 backup_dir | backup 主流程直接产出 |

## 四、治理规则

- 新增错误码或警告码时，必须先补本文档，再进入前端聚合或测试口径。
- 若历史实现中的前缀与默认严重级别不一致，以 `default_severity` 为准解释。
- 若未来需要更细严重级别，可在不改列结构的前提下扩展枚举值。
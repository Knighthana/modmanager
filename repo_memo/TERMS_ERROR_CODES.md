# Error Codes Freeze

> Status: active
> Authority: authoritative
> Read-Tier: always
> Purpose: 统一记录 backupinfo、backup、restore 相关错误码与默认严重级别，供后端、前端、测试与后续 i18n 共用

## 一、用途与边界

- 本文档是错误码与警告码的统一入口。
- 任何新引入的 backupinfo、backup、restore 相关 `E_` / `W_` 码，都应先或同步登记到这里。
- 前缀与默认严重级别必须一致：`E_` 对应 `error`，`W_` 对应 `warning`。

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
| `W_EXTERNAL_FILE_ORPHAN` | `restore` | 检测到本次 restore 未命中的外部文件或孤儿文件 | `warning` | 外部孤儿文件提示 | 不阻断 restore 主流程 |
| `E_BACKUP_COPY_FAILED` | `backup` | 将目标文件复制进 backup_dir 失败 | `error` | 备份复制失败 | 当前条目未成功写入 backup |
| `E_APPLY_MISSING_TARGET` | `apply` | apply 条目缺少目标路径或目标路径为空 | `error` | apply 目标路径缺失 | 属于 apply 输入或执行前检查失败 |
| `E_APPLY_MISSING_SOURCE` | `apply` | apply 条目缺少源路径，或无法定位源文件 | `error` | apply 源路径缺失 | delete 哨兵 `!` 不适用本条 |
| `W_APPLY_DIR_NO_MATCHED_ENTRIES` | `apply` | 某个 apply 处理单元没有匹配到可执行条目 | `warning` | 当前处理单元没有可应用条目 | 不阻断其它处理单元 |
| `W_APPLY_NO_EFFECT` | `apply` | 本次 apply 未真正应用任何条目 | `warning` | 当前 apply 没有产生实际效果 | 用于提示空执行或全部被跳过 |

## 三、使用约束

- 设计文档描述 warning / error 时，应引用本文档，而不是各自重复定义严重级别。
- 前端聚合展示、筛选、分组、i18n 映射时，应以本文档字段为准。
- 测试组校对错误码含义时，应以本文档为准，而不是反向阅读代码猜测。
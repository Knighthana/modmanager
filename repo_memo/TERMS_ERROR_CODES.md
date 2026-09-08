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
| `E_BACKUP_COPY_FAILED` | `backup` | 将目标文件复制进 backup_dir 失败 | `error` | 备份复制失败 | 当前条目未成功写入 backup |
| `E_APPLY_MISSING_TARGET` | `apply` | apply 条目缺少目标路径或目标路径为空 | `error` | apply 目标路径缺失 | 属于 apply 输入或执行前检查失败 |
| `E_APPLY_MISSING_SOURCE` | `apply` | apply 条目缺少源路径，或无法定位源文件 | `error` | apply 源路径缺失 | delete 哨兵 `!` 不适用本条 |
| `W_APPLY_DIR_NO_MATCHED_ENTRIES` | `apply` | 某个 apply 处理单元没有匹配到可执行条目 | `warning` | 当前处理单元没有可应用条目 | 不阻断其它处理单元 |
| `W_APPLY_NO_EFFECT` | `apply` | 本次 apply 未真正应用任何条目 | `warning` | 当前 apply 没有产生实际效果 | 用于提示空执行或全部被跳过 |
| `E_APPLY_NOT_FILE` | `apply` | apply 目标路径不具备文件语义（以 `/` 结尾） | `error` | apply 目标不是文件 | file-to-file 守卫 |
| `E_APPLY_DIRECTORY_NOT_ALLOWED` | `apply` | apply 源/目标路径实际是目录 | `error` | apply 目标是目录 | file-to-file 守卫 |
| `E_APPLY_PERMISSION` | `apply` | apply 执行时权限不足 | `error` | apply 权限失败 | 当前条目失败，不阻断其它条目 |
| `E_APPLY_FAILED` | `apply` | apply 执行时发生其它 I/O 失败 | `error` | apply 执行失败 | 当前条目失败，不阻断其它条目 |
| `W_RESTORE_NOT_BACKED_UP` | `restore` | 树上对应结点 `isbackuped=false` | `warning` | 该文件未备份，跳过恢复 | DESIGN_RESTORE_OPS §四-4 |
| `W_RESTORE_INVALID_HASH` | `restore` | 树上结点 `hashtype=invalid` 或 `hashvalue=0` | `warning` | 该文件无有效 hash，跳过恢复 | DESIGN_RESTORE_OPS §四-4 |
| `W_RESTORE_NO_BACKUP_COPY` | `restore` | backup_dir 中找不到可恢复实体 | `warning` | 无备份副本，跳过 | 不隐式成功 |
| `E_RESTORE_NOT_FILE` | `restore` | 恢复目标路径实际是目录 | `error` | 恢复目标不是文件 | file-to-file 守卫 |
| `E_RESTORE_DELETE_FAILED` | `restore` | 树上无结点时删除源文件失败 | `error` | 恢复删除失败 | DESIGN_RESTORE_OPS §四-3 |
| `E_RESTORE_PERMISSION` | `restore` | 恢复复制时权限不足 | `error` | 恢复权限失败 | 当前条目失败，不阻断其它条目 |
| `E_RESTORE_FAILED` | `restore` | 恢复复制时发生其它 I/O 失败 | `error` | 恢复执行失败 | 当前条目失败，不阻断其它条目 |
| `W_BACKUP_NODE_NOT_IN_TREE` | `backup` | 待备份文件在树上没有对应结点 | `warning` | 不属于该目录，跳过备份 | 不允许改树，DESIGN_BACKUP_OPS §六-2 |
| `W_BACKUP_DIR_BUILD_NO_MATCH` | `backup-dir` | mapping 目标路径未匹配任何 game 条目 | `warning` | 该目标无归属 backup_dir | 该条目被排除在本次操作之外 |
| `W_IGNORE_FILTERED` | `planner` | 条目被 kmmignore（含硬编码层）过滤 | `warning` | 有条目被忽略规则排除 | 计数展示 |
| `W_BAKIGNORE_FILTERED` | `planner` | 条目被 bakignore（源侧后缀匹配）过滤 | `warning` | 有条目被 bakignore 排除 | 仅 BACKUP intent；见 DESIGN_KMMIGNORE_RULES §七 |
| `W_PREFLIGHT_FAILED` | `planner` | preflight 门禁未通过 | `warning` | 前置检查失败 | 原语不会执行 |
| `W_PATH_CASE_MISMATCH` | `engine` | 规则路径大小写与文件系统实际条目不一致 | `warning` | 提示规则作者修正大小写 | 只报告不改写（2026-09-08 裁决）；设计见 DESIGN_PATH_CASE |
| `E_BAD_INTENT` | `orchestrator` | dispatch 收到未知 intent | `error` | 非法意图 | 编程性错误 |
| `E_RESOLVE_FAILED` | `orchestrator` | Resolver 解析失败 | `error` | 上下文解析失败 | dispatch 顶层捕获 |
| `E_FETCH_FAILED` | `orchestrator` | DataPort.fetch 失败 | `error` | 数据读取失败 | dispatch 顶层捕获 |

## 三、使用约束

- 设计文档描述 warning / error 时，应引用本文档，而不是各自重复定义严重级别。
- 前端聚合展示、筛选、分组、i18n 映射时，应以本文档字段为准。
- 测试组校对错误码含义时，应以本文档为准，而不是反向阅读代码猜测。
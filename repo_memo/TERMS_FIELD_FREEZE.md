# 字段冻结记录

> Status: stable
> Authority: authoritative
> Read-Tier: always
> Purpose: 冻结关键字段名与输出结构，作为命名与契约修改的门禁

## 当前冻结字段

| 字段 | 类型 | 说明 | 冻结日期 |
|------|------|------|---------|
| `contains_libraryfolders_vdf` | — | — | — |
| `OS.workingpathstyle` / `OS.steamlibpathstyle` | — | — | — |
| `steamlib[].game` | — | — | — |
| `game[].mods_found` | — | — | — |
| `mod[].mixed_id` | — | — | — |
| `mod[].managed` | — | — | — |
| `game[].managed` | — | — | — |
| `workspace_id` | `string` | 后端生成的工作区唯一标识（SHA256 截取前 24 字符） | 2026-05-16 |
| `workspace_dir` | `string \| null` | user_config 中配置的工作区根目录，`null` 时使用平台默认 | 2026-05-16 |
| `currentWorkspaceId` | `string \| null` | 前端 sessionStorage 中存储的当前活跃工作区 ID | 2026-05-16 |
| `decisions.managed_entries` | `object` | 用户对重复条目的路径筛选 `{ game: {appid: [path]}, mod: {mixed_id: [path]} }` | 2026-05-16 |
| `decisions.branch_decisions` | `object` | 冲突裁决映射 `{ root_path: chosen_source_path }` | 2026-05-16 |
| `backupinfo.tree_created_time` | `string` | 首次建树时刻（prep 写入后不再修改），ISO8601 date-time | 2026-05-23 |
| `backupinfo.last_modified_time` | `string` | backupinfo 最后一次被本项目工具写入的时间 | 2026-05-19 |
| `backupinfo.schema_version` | `string` | backupinfo schema 版本号 | 2026-05-19 |
| `backupinfo.tree` | `DirNode` | backupinfo 的冻结全量快照树 | 2026-05-19 |
| `backupinfo.tree[].type` | `"dir" \| "file"` | backupinfo 节点类型，目录语义统一用 dir | 2026-05-19 |
| `backupinfo.dir.name` | `string` | DirNode 名称字段 | 2026-05-19 |
| `backupinfo.dir.children` | `array` | DirNode 子节点字段 | 2026-05-19 |
| `backupinfo.file.name` | `string` | FileNode 名称字段 | 2026-05-19 |
| `backupinfo.file.isbackuped` | `boolean` | FileNode 是否已完成备份 | 2026-05-19 |
| `backupinfo.file.hashtype` | `string` | FileNode hash 算法类型 | 2026-05-19 |
| `backupinfo.file.hashvalue` | `string` | FileNode hash 值 | 2026-05-19 |

## 输出结构冻结
- compute_mapping 输出 key: `"trees"`（数组），`"final_mapping"`（数组）
- TreeNode: `root_path`, `destin_mixed_id`, `changerequest`, `refs`, `resolved_state`
- ChangeRequest: `path`, `action`, `mixed_id`, `hashtype`, `hashvalue`
- FinalMappingEntry: `path`, `request`

## backupinfo 结构冻结
- 根字段：`schema_namespace`, `tree_created_time`, `last_modified_time`, `schema_version`, `tree`
- `tree` 根节点类型必须为 `dir`
- `DirNode`: `name`, `type`, `children`
- `FileNode`: `name`, `type`, `isbackuped`, `hashtype`, `hashvalue`
- backupinfo 目录语义统一使用 `dir`



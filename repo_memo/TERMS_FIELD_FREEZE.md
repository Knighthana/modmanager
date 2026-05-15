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

### 已废弃字段（2026-05-16 移除）

以下字段随旧 localStorage 工作区模型一并废除。新模型使用后端工作区目录管理。

| 字段 | 原说明 | 废弃原因 |
|------|------|----------|
| `lastDatabase` | 全局 database 选中 | 工作区绑定 database，创建时选定 |
| `selectedRulePaths` | 用户选定的规则文件路径列表 | 聚合结果直接存入工作区 |
| `managedEntries`（localStorage） | 前端持久化的重复条目筛选 | 迁移到工作区 `decisions.json` |
| `branchDecisions`（localStorage） | 前端持久化的冲突裁决 | 迁移到工作区 `decisions.json` |
| `lastComputeSummary` | 前端持久化的计算摘要 | 迁移到工作区 `mapping.json` |
| `aggregatedRuleMeta.*` | 前端持久化的聚合缓存 | 规则集直接存入工作区，指纹校验后端管理 |

## 输出结构冻结
- compute_mapping 输出 key: `"trees"`（数组），`"final_mapping"`（数组）
- TreeNode: `root_path`, `destin_mixed_id`, `changerequest`, `refs`, `resolved_state`
- ChangeRequest: `path`, `action`, `mixed_id`, `hashtype`, `hashvalue`
- FinalMappingEntry: `path`, `request`



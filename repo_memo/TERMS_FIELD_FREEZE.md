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
| `lastDatabase` | `string \| null` | 当前选中的 database name | — |
| `selectedRulePaths` | `string[]` | 用户选定的规则文件路径列表 | 2026-05-14 |
| `managedEntries` | `object` | 用户对重复条目的路径筛选 `{ game: {appid: [path]}, mod: {mixed_id: [path]} }` | 2026-05-14 |
| `branchDecisions` | `object` | 冲突裁决映射 `{ root_path: chosen_source_path }` | 2026-05-14 |
| `lastComputeSummary` | `object` | 上次计算摘要 `{ treesCount, mappingCount, warnings, errors, inputsHash, timestamp }` | 2026-05-14 |
| `aggregatedRuleMeta.output_path` | `string` | 聚合产物文件路径（用于刷新后恢复） | — |
| `aggregatedRuleMeta.aggregated_hash` | `string` | 聚合结果 hash（用于一致性校验） | — |
| `aggregatedRuleMeta.aggregated_at` | `string` | 聚合完成时间（ISO 8601） | — |
| `aggregatedRuleMeta.selected_rule_paths` | `string[]` | 本次聚合使用的规则路径列表 | — |

## 输出结构冻结
- compute_mapping 输出 key: `"trees"`（数组），`"final_mapping"`（数组）
- TreeNode: `root_path`, `destin_mixed_id`, `changerequest`, `refs`, `resolved_state`
- ChangeRequest: `path`, `action`, `mixed_id`, `hashtype`, `hashvalue`
- FinalMappingEntry: `path`, `request`



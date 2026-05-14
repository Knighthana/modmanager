# 字段冻结记录

> Status: stable
> Authority: authoritative
> Read-Tier: always
> Purpose: 冻结关键字段名与输出结构，作为命名与契约修改的门禁

## 当前冻结字段
- `contains_libraryfolders_vdf`
- `OS.workingpathstyle` / `OS.steamlibpathstyle`
- `steamlib[].game`
- `game[].mods_found`
- `mod[].mixed_id`
- `mod[].managed`
- `game[].managed`
- `lastDatabase` — 当前选中的 database name（字符串）
- `selectedRulePaths` — 用户选定的规则文件路径列表（string[]）
- `managedEntries` — 用户对重复条目的路径筛选（object：{game: {...}, mod: {...}}）
- `branchDecisions` — 冲突裁决的决策映射（object：{root_path: chosen_source}）
- `aggregatedRuleMeta.output_path` — 聚合产物文件路径（用于刷新后恢复）
- `aggregatedRuleMeta.aggregated_hash` — 聚合结果 hash（用于一致性校验）
- `aggregatedRuleMeta.aggregated_at` — 聚合完成时间（ISO 8601）
- `aggregatedRuleMeta.selected_rule_paths` — 本次聚合使用的规则路径列表

## 输出结构冻结
- compute_mapping 输出 key: `"trees"`（数组），`"final_mapping"`（数组）
- TreeNode: `root_path`, `destin_mixed_id`, `changerequest`, `refs`, `resolved_state`
- ChangeRequest: `path`, `action`, `mixed_id`, `hashtype`, `hashvalue`
- FinalMappingEntry: `path`, `request`



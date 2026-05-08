# 字段冻结记录

> Status: stable
> Authority: authoritative
> Read-Tier: always
> Purpose: 冻结关键字段名、输出结构与已废弃字段，作为命名与契约修改的门禁

## 当前冻结字段
- `contains_libraryfolders_vdf`
- `OS.workingpathstyle` / `OS.steamlibpathstyle`
- `steamlib[].game`
- `game[].mods_found`
- `dommod[].mixed_id`

## 输出结构冻结
- compute_mapping 输出 key: `"trees"`（数组），`"final_mapping"`（数组）
- TreeNode: `root_path`, `destin_mixed_id`, `changerequest`, `refs`, `resolved_state`
- ChangeRequest: `path`, `action`, `mixed_id`, `hashtype`, `hashvalue`
- FinalMappingEntry: `path`, `request`

## 已废弃字段（禁止使用）
- ~~islbfdvdflocate~~
- ~~appitemid~~
- ~~itemid（若表示 mod 列表）~~
- ~~forest（已改为 trees）~~

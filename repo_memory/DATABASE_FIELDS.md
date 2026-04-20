# Database Field Dictionary

## Top-Level
- `OS` (object)
- `steamlib` (array)
- `game` (array)
- `dommod` (array, optional)
- `history` (object, optional)

## OS
- `workingpathstyle`: string, enum {"linux", "windows"}
- `steamlibpathstyle`: string, enum {"linux", "windows"}

## steamlib[]
- `path`: string, absolute path to `steamapps`
- `contains_libraryfolders_vdf`: boolean
- `game`: array[string], appid list for this library

## game[]
- `appid`: string
- `name`: string
- `localdate`: number
- `basepath`: string
- `modpath`: string
- `mods_found`: array[string]

## dommod[]
- `mixed_id`: string (`appid:modid`)
- `localdate`: number
- `path`: string

## history
- UI 状态容器，结构可扩展

## Compatibility
- 禁止新增历史别名字段：`islbfdvdflocate`, `islbfvdflocate`, `appitemid`
- `itemid` 若表示 mod 列表，统一迁移为 `mods_found`

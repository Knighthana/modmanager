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

### steamlib CRUD（强制能力）
- `create`: 新增手动指定库路径（永远允许）
- `read`: 查询当前库路径列表与来源状态
- `update`: 修改库路径并同步相关 `game` / `dommod` 路径
- `delete`: 删除库路径并级联移除不再归属任何库的 `game` / `dommod`

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

## Update Interfaces
- `liveupdate`: 增量扫描现有 `steamlib`，仅按变化更新 `game` 与 `dommod`
- `regen`: 清空 `game` 与 `dommod`，按最新 `steamlib` 全量重建

## Compatibility
- 禁止新增历史别名字段：`islbfdvdflocate`, `islbfvdflocate`, `appitemid`
- `itemid` 若表示 mod 列表，统一迁移为 `mods_found`

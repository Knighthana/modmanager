# Document Contract Snapshot

更新时间：2026-04-21

## 冻结结论
1. 主发现字段固定为 `contains_libraryfolders_vdf`
2. 组合标识字段固定为 `mixed_id`
3. 游戏 mod 列表字段固定为 `mods_found`
4. 路径风格字段固定为 `OS.workingpathstyle` 与 `OS.steamlibpathstyle`

## 历史名处理
- `islbfdvdflocate` / `islbfvdflocate`：废弃
- `appitemid`：废弃，统一 `mixed_id`
- `itemid`（mod 列表语义）：废弃，统一 `mods_found`

## 实现对齐优先级
1. 先修 discovery pipeline
2. 再修 database 输出字段
3. 再补集成测试

## 执行状态（2026-04-21）
1. 已完成：主 VDF 扩展发现全部库。
2. 已完成：`steamlib[].game` 输出落位。
3. 已完成：默认非贪婪过滤与 `greedy_parsing` 放宽行为实现。
4. 已完成：对应测试断言新增并通过。
5. 已完成：治理硬约束补丁落盘（违规后果、Plan 授权例外、迁移完成度模板）。
6. 已完成：VDF 解析三项修复（根 key 大小写兼容、apps/games 双 key 兼容、path 自动追加 steamapps）。

## 测试快照（2026-04-21）
- `tests.test_steam_scanner`：19/19 通过
- 全量：134/134 通过

## 回归复测（2026-04-21）
- `tests.test_steam_scanner`：21/21 通过（新增 apps key + steamapps 后缀测试）
- `unittest discover -s tests -p test_*.py`：136/136 通过
- WSL 实机：3 库 / 86 游戏 / 73 mod（E 盘不存在时静默返回，无异常）

## 来源
- `repo_memory/TERMINOLOGY.md`
- `repo_memory/STEAM_DISCOVERY.md`
- `repo_memory/DATABASE_FIELDS.md`

# Document Contract Snapshot

更新时间：2026-04-21

## 冻结结论
1. 主发现字段固定为 `contains_libraryfolders_vdf`
2. 组合标识字段固定为 `mixed_id`
3. 游戏 mod 列表字段固定为 `mods_found`
4. 路径风格字段固定为 `OS.workingpathstyle` 与 `OS.steamlibpathstyle`
5. 自动发现失败时必须回退手动指定并继续流程
6. 永远允许用户手动指定 `steamapps` 目录
7. 不以“完整/不完整”作为发现判定条件，仅在无可用工作目录时要求用户介入
8. `steamlib` 必须提供 CRUD；并提供 `liveupdate` 与 `regen` 两个维护接口

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
7. 已完成：手动指定能力与数据维护接口契约冻结（CRUD/liveupdate/regen）。
8. 已完成：`database_ops` 接口落地（discover_with_fallback、steamlib/game CRUD、liveupdate、regen、integrity check）。

## 测试快照（2026-04-21）
- `tests.test_steam_scanner`：19/19 通过
- 全量：134/134 通过

## 回归复测（2026-04-21）
- `tests.test_steam_scanner`：21/21 通过（新增 apps key + steamapps 后缀测试）
- `unittest discover -s tests -p test_*.py`：136/136 通过
- WSL 实机：3 库 / 86 游戏 / 73 mod（E 盘不存在时静默返回，无异常）

## 接口回归（2026-04-21）
- `tests.test_database_ops`：8/8 通过
- `unittest discover -s tests -p test_*.py`：144/144 通过

## 备份/替换/恢复模块回归（2026-04-21）

- 全量测试：189/189 通过
- 新增模块：`backup_ops.py`（Phase 7-12 实现）
- 新增测试：`test_backup_ops.py`（36 个测试，全部通过）
- CLI 新增命令：`backup`、`apply`、`restore`
- M1 核心文件未修改，adapter 层通过调用 M1 实现编排

## Phase 13 脏数据/冲突治理回归（2026-04-21）

- 全量测试：194/194 通过
- `backup_ops.py` 新增：`detect_dirty_state`、`inspect_conflict`、`delete_orphan_files`
- `restore_from_backup` 扩展：返回 `orphans` 与 `warnings`，默认仅报告 orphan
- CLI 新增：`restore --delete-orphans`（显式开关触发删除）
- 决策落盘：路径进入边界后立即规范化；执行时序为“计算 -> 建树备份 -> 替换 -> 恢复/冲突治理”


- `tests.test_cli_database_ops`：9/9 通过
- `unittest discover -s tests -p test_*.py`：153/153 通过
- 已完成：CLI 异常出口统一（输入读取失败、liveupdate/regen 失败、输出写入失败统一返回 code=2）
- 已完成：legacy 模式 `result.errors` 缺省兼容（`result.get("errors", [])`）
- 待跟踪：如需对外发布，补充 CLI 用户文档示例与 game CRUD CLI 对齐

## 来源
- `repo_memory/TERMINOLOGY.md`
- `repo_memory/STEAM_DISCOVERY.md`
- `repo_memory/DATABASE_FIELDS.md`

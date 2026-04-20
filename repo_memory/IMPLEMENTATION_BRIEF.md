# Implementation Agent Brief

## Status Board

更新时间：2026-04-21

| 任务 | 状态 | 验收 | 备注 |
|---|---|---|---|
| 文档入口迁移到 repo_memory | done | `README.md` 明确入口 | 已完成 |
| discovery pipeline 扩展多库 | done | `discover_steam_libraries` 解析主 VDF 并扩展库 | 已完成 |
| database 输出 `steamlib[].game` | done | 结构中存在 `steamlib[].game` | 已完成 |
| 默认非贪婪过滤闭环 | done | 非 VDF 范围 appid 默认不解析 mod | 已完成 |
| greedy_parsing 放宽过滤 | done | 打开后允许解析范围外 appid mod | 已完成 |
| 同步索引与持久化摘要 | done | `MEMORY_SYNC_INDEX.md` 与 3 个摘要文件存在 | 已完成 |
| 治理硬约束补丁 | done | README/Brief/SyncIndex 明确执行门禁与例外流程 | 已完成 |
| VDF 根 key 大小写兼容 | done | 兼容 `"libraryfolders"` 与 `"LibraryFolders"` | 已完成 |
| VDF apps/games key 兼容 | done | 兼容现代 `"apps"` 与旧版 `"games"` 子块 | 已完成 |
| VDF path 自动追加 steamapps | done | Steam 根目录路径扩展时自动拼接 `steamapps` 后缀 | 已完成 |

## 本轮任务目标
在不改业务逻辑前提下，先完成文档契约对齐；随后按契约修复实现与测试。

## 执行边界
- 第一阶段：仅改 `repo_memory/` 与示例契约
- 第二阶段：再改 `src/` 与 `tests/`

## 需求来源硬约束（P0）
1. 实现与测试的需求来源优先级固定为：Plan 指令 > `repo_memory/` > 代码注释。
2. `description/` 仅可作为历史样例，不得直接作为实现依据。
3. 若 `repo_memory/` 与 `description/` 冲突，必须按 `repo_memory/` 执行，并把差异写入 `MEMORY_SYNC_INDEX.md`。
4. 未满足以上三条时，任务状态必须标记为 blocked，不得继续开发。

## 第一阶段交付物
1. 术语冻结：`TERMINOLOGY.md`
2. 扫描契约：`STEAM_DISCOVERY.md`
3. 字段字典：`DATABASE_FIELDS.md`
4. 流程总览：`process_description.md`
5. 快照记录：`doc_contract_snapshot.md`

## 第二阶段（实现）必改点
1. `discover_steam_libraries` 必须从主 VDF 扩展发现全部库
2. `generate_database` 必须输出 `steamlib[].game`
3. `steamlibpathstyle` 来源应以 VDF 解析结果为主，不应仅靠首路径猜测
4. 默认保持非贪婪解析

## 第二阶段（测试）必补点
1. 主 VDF 扩展发现 D/E 盘库的集成测试
2. `database` 输出包含 `steamlib[].game` 的断言
3. 默认忽略不在 VDF 游戏列表范围内 appworkshop 的测试

## 执行顺序
1. 先更新 `repo_memory` 契约与同步索引。
2. 再改 `src/` 的非贪婪/贪婪逻辑。
3. 最后补测试并跑全量回归。

## 验收标准
- 字段主名唯一
- 文档、实现、测试三方字段一致
- 能复现并修复“只发现默认 C 盘库”的历史问题

## 本轮结果
- 扫描专项测试：21/21 通过
- 全量测试：136/136 通过
- 治理补丁：已落盘并通过回归验证
- WSL 实机扫描：3 库 / 86 游戏 / 73 mod（C/D/E 三盘全部发现）

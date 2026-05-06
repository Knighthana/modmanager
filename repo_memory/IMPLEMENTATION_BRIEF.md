# Implementation Agent Brief

## Status Board

更新时间：2026-05-06

| 任务 | 状态 | 验收 | 备注 |
|---|---|---|---|
| **P3: GUI 增强** | **done** | 322+18 tests 通过 | 全部/仅分岔 + hover 整链高亮 + 点击选枝 |
| **P2: 引擎细节修复** | **done** | 320 tests 通过 | delete→create warning + 术语统一 |
| **P1: Backup 实现** | **done** | 319 tests 通过 | backup_dir_builder + 循环防护 + .kmmbakignore |
| **P0: 森林模型重构** | **done** | 296 tests 通过 | 独立根+引用，`forest`→`trees`，自底向上解析 |
| Phase 3: 前端 GUI | **done** | 276+14 tests 通过 | Vue 3 SPA + Forest SVG 交互 + 冲突裁决 + 规则/备份页面，frontend/ 构建嵌入 FastAPI |
| Phase 2: Web API 层 | **done** | 276 测试全部通过 | `modmanager_web` 独立子包，FastAPI + SSE，15 new tests，`modmanager/*` 零改动 |
| Phase 1: Bootstrap & Orchestration | **done** | 261 测试全部通过 | bootstrap.py + orchestrator.py + CLI 适配 + 18 new tests |
| 聚合器 + M1 引擎重构 | done | 243 测试全部通过 | commit `0a145f4` |
| 同 mod 冲突自动裁决 | done | 120→0 冲突 | commit `428bb79` |
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
| 手动指定库路径强制回退 | done | 自动发现失败时可回退手动指定并继续流程 | 已完成 |
| steamlib CRUD 接口 | done | 已提供增删改查与级联维护 | 已完成 |
| liveupdate / regen 接口 | done | 增量更新与全量重建接口可调用 | 已完成 |
| CLI 对外暴露（steamlib/liveupdate/regen） | done | 命令入口可调用并写回数据库 | 已完成 |
| CLI 稳健性收敛（异常统一出口） | done | 错误场景统一返回 code=2 且输出可读错误 | 已完成 |

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
- 数据库维护接口测试：8/8 通过
- CLI 维护接口测试：9/9 通过
- 全量测试：153/153 通过
- 治理补丁：已落盘并通过回归验证
- WSL 实机扫描：3 库 / 86 游戏 / 73 mod（C/D/E 三盘全部发现）

## 备份/替换/恢复模块（Phase 7-12）

| 任务 | 状态 | 验收 | 备注 |
|---|---|---|---|
| Phase 7: backup_id 生成（acf LastUpdated→hex） | done | `get_game_backup_id` 可调用 | 已完成 |
| Phase 8: filefoldertree 建树 + sha256 | done | `build_filefoldertree_with_hashes` 可调用 | 已完成 |
| Phase 8: backup 目录生命周期（init/finalize） | done | status: error→ready | 已完成 |
| Phase 9: 替换前门禁（backup gate） | done | `check_backup_gate` 返回错误码 | 已完成 |
| Phase 10: 差异备份执行 | done | `run_differential_backup` 可调用 | 已完成 |
| Phase 11: final_mapping 替换执行 | done | `apply_final_mapping` 含 gate 检查 | 已完成 |
| Phase 12: 从备份恢复 | done | `restore_from_backup`，hash 一致跳过 I/O | 已完成 |
| Phase 13: 脏数据/冲突治理 | done | dirty-state 检测 + conflict 检查 + orphan 报告/可选删除 | 已完成 |
| CLI backup/apply/restore 命令 | done | 命令入口可调用 | 已完成 |
| CLI restore --delete-orphans | done | 手动确认后删除 orphan，默认仅报告 | 已完成 |

## 本轮结果（Phase 13）
- 新增能力：`detect_dirty_state`、`inspect_conflict`、orphan 报告与 `delete_orphan_files`
- CLI：`restore` 新增 `--delete-orphans`，默认保守策略（只报告不删除）
- 测试：`tests.test_backup_ops` 41/41 通过
- 全量：194/194 通过

## 开放冲突关闭记录

| 冲突 | 结论 | 状态 |
|---|---|---|
| #2 hash 占位与合法值边界 | 两阶段校验：写入仅检查不倒退，展示层按 invalid/0 vs sha256/hex 渲染 | closed 2026-04-21 |
| #3 filefoldertree 结构冻结 vs 属性演进 | 结构冻结 + 仅 file 节点三字段单向变更，其余拒绝并报错 | closed 2026-04-21 |

实现验证：`engine._check_filefoldertree_transition` 已完全符合两项决策，无需改代码。
全量回归：194/194（验证于 d1743be，关闭冲突为纯文档操作）。

## 下一轮执行清单（收敛）
1. 视发布需求决定是否补齐 game CRUD CLI 对外命令。
2. 增加一条 CLI `--out` 文件真实 I/O 集成用例（liveupdate/regen）。
3. 若对外发布，补 CLI 用户文档（最小示例 + 错误码说明）。

## 新增阶段策略（2026-04-22）
1. 今天不改 M1：近期演示阶段优先保持 M1 稳定。
2. 先在 M1 外实现：replace_service、backup_dir_builder、rule aggregation sidecar。
3. 未来可并入 M1：当外层机制稳定后，将 `provenance_ref`、`action_order`、`sidecar_ref` 传导等能力并入引擎主链。
4. `_ref` 缺失或空值时统一回退为 `404` 并记录 warning，不允许直接崩溃。
5. `description/` 仅用于 user-plan 交流；implement 默认以 `repo_memory/` 为标准源。
6. delete 在当前 forest 模型中视为无 source-path 的叶请求；若最终有效叶为 delete，则折叠为对根 target 的删除请求并在执行阶段删除该目标文件。

## 历史映射风险定义（replace）
1. 风险核心：避免“本该使用 A 的位置误用为 E”。
2. 典型情形：目录外同名 A 实际已被历史替换覆盖，当前可见文件名与语义不一致。
3. 处置原则：替换执行前由历史映射解析层给出“当前有效源”，replace 接口只执行，不裁决。

## Forest 视觉表达近期范围（2026-04-22）
1. 近期仅实现四部分：`forest_visual` 核心模块、ASCII renderer、DOT renderer、DOT -> SVG renderer。
2. 近期目标是“先让人能看到 forest 的形状”，不是完成 GUI。
3. 可视化模块保持独立后处理，不修改 `compute_mapping` 主链与当前 `output_schema`。
4. 未来 M1 patch 可能为 `forest` / `changerequest` 增加 trace/meta 标签；可视化设计必须兼容未知扩展字段，避免字段绑定过死。

## Forest 可视化里程碑排期（2026-04-22）
1. 近期：core + ASCII + DOT + DOT -> SVG。
2. M3：HTML fragment、HTML standalone、Plot renderer、trace/meta 可视化兼容验证。
3. M4：GUI hover 整链高亮、分叉节点超链接、用户选枝 UI、插件运行链、老浏览器 fallback。

## Forest 可视化开工门槛（文档先行）
1. 实现前必须先阅读 `FOREST_VISUALIZATION_DESIGN.md` 的数据流、坑位清单、Go/No-Go 与验收用例。
2. 本轮若仅做文档持久化，不允许改动 `src/`、`tests/`、`pyproject.toml`。

## aggregated_rule_set DSL 冻结（2026-04-22）
1. M1 近期只接收 `aggregated_rule_set`；单条 `kmm_rule` 的聚合发生在 M1 外。
2. `from` 与 `into` 在规则层统一为 `list[string]`；不再接受 string 或 string|list 混写。
3. 非 `hold` 且非 `delete` 的 action，必须显式提供 `from_type` 与 `into_type`，取值仅允许 `file` 或 `path`。
4. `delete` 只读取 `into` 与 `into_type`；`from` 与 `from_type` 完全忽略，写了也无效。
5. 若 `_type=path`，则对应列表中的每一项都必须以 `/` 结尾；否则直接报错。
6. `into_type=file` 时，`from_type` 必须为 `file`；不接受 path -> file 兜底。
7. 若单条 action 的 `from` 为多值或包含 glob，则同条 action 的 `into` 不得为多值；系统不做笛卡尔扩展。
8. `path -> path` 的语义固定为复制目录本身，即 `cp -r src/ dest/` 产出 `dest/src/`。
9. `from_type=file` 的 glob 只匹配文件，不隐式携带目录递归或“文件+目录混合命中”语义。
10. 若想表达 `cp -r src/* dest/` 的效果，必须拆成两条 action：一条 `from=["src/*/"] + from_type=path` 复制目录项，一条 `from=["src/*"] + from_type=file` 复制文件项。
11. 当 `from_type=path` 且 `from` 含 glob（例如 `shiplander v1.9/*/`）时，展开单位是目录实体；每个命中的目录各自生成一个目标目录映射，例如 `maps/src1/`、`maps/src2/`、`maps/src3/`。

## action 解析与校验分流（2026-04-22）
1. 校验绑定在 action 处理路径上，不使用一个覆盖全部 action 的大一统校验器。
2. `replace` 与 `create` 共享同一套写入型校验流程；以后若差异扩大再拆分。
3. `delete` 使用独立校验流程，仅检查 `into` 与 `into_type`。
4. ~~`rename_then_replace` 与 `clear_then_copy` 复用写入型校验，再追加各自的兼容字段约束。~~（已废弃 2026-04-30）
5. 明确禁止把相同前置条件的校验逻辑复制到多个 action 分支中。

## hold 规则（2026-04-22；2026-04-30 移交至聚合器）
> 自 2026-04-30 起，`def_action` 继承解析和 hold 过滤已移交**聚合器**执行。
> M1 引擎收到的 `aggregated_rule_set` 中每个 action 的 `action` 和 `destin` 均为显式值，
> 不再存在 `def_action`/`def_destin` 字段和 hold action。

1. 只有最终解析结果为 `hold` 的 action 才会被跳过。（现由聚合器在输出前执行）
2. 跳过的定义是：不校验、不解析、不展开、不参与冲突分析、不进入 final mapping。
3. 若父级 `def_action=hold`，且子 action 未显式声明 `action`，则该子 action 继承为 `hold` 并被直接忽略。（现由聚合器具体化阶段完成）
4. 若父级 `def_action=hold`，但子 action 显式声明了非 `hold` action，则以子 action 为准，按对应流程正常校验与解析。
5. 任意对象中显式写出的 `action=hold` 条目，同样直接忽略。

## 冲突分层（2026-04-22）
1. 同一 `mixed_id`、同一 `actionlist` 内，按书写顺序执行。
2. 同一 action 展开后若多个源命中同一目标文件，直接报 `E_ACTION_INTERNAL_COLLISION`。
3. `delete` 与非 `delete` 若在同批次命中同一目标，直接报错，不做隐式抵消。
4. 不同 `mixed_id` 之间的冲突仍进入 branch 系统处理。

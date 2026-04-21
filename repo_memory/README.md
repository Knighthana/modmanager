# repo_memory

本目录是当前阶段的工作指挥与契约冻结区。

## 目标
- 将实现指挥从 `description/` 迁移到 `repo_memory/`
- 固化术语、字段命名与扫描流程
- 为后续实现和测试修复提供唯一参考

## 使用顺序
1. 先读 `TERMINOLOGY.md`
2. 再读 `STEAM_DISCOVERY.md`
3. 再读 `DATABASE_FIELDS.md`
4. 按 `IMPLEMENTATION_BRIEF.md` 执行

## 同步规则
- `description/` 仅作为用户与 Plan 的沟通目录，不作为 implement 默认输入
- 当前实现与契约以 `repo_memory/` 为准
- `json.example` 采用单向同步：`repo_memory/` -> `description/`
- implement 禁止将 `description/` 反向写回 `repo_memory/`

## 角色职责矩阵

| 角色 | description | repo_memory | work_memo |
|---|---|---|---|
| user | 读/写 | 可读 | 不使用 |
| plan | 读/写 | 读/写（主维护） | 可读（必要时） |
| implement | 默认忽略；仅在 Plan 明确任务下写入 | 必读（实现指导） | 读/写（自管临时记忆） |

说明：`work_memo/` 为 implement 的临时工作区，不进入契约决策链，不作为字段或流程依据。

## 执行门禁
1. 实现任务必须引用本目录中的文档路径；缺失路径视为无效任务单。
2. 实现阶段不得以 `description/` 推导新规则，只可根据 `repo_memory/` 与 Plan 指令执行。
3. 涉及字段命名变更时，必须先更新 `TERMINOLOGY.md` 与 `DATABASE_FIELDS.md`，再改 `src/` 与 `tests/`。
4. 若 `repo_memory/` 与 `description/` 冲突，以 `repo_memory/` 为准，并将差异记录到 `MEMORY_SYNC_INDEX.md`。

## 违规后果
1. 发现以 `description/` 作为实现依据的提交，直接判定为无效实现，必须回滚并重做。
2. 未先更新契约文档即修改字段名的提交，禁止合并，需补齐文档与测试后重新评审。
3. 未记录冲突差异的提交，视为流程不合规，状态板降级为 blocked。

## Plan 授权例外流程
1. 仅当 Plan 明确写出例外范围时，允许临时引用 `description/` 作为补充背景。
2. 例外任务必须在任务单中写明：授权来源、有效期、影响字段、回收动作。
3. 例外结束后，必须在 `MEMORY_SYNC_INDEX.md` 追加回收记录；未回收前不得进入下一阶段。

## 字段主名（冻结）
- `contains_libraryfolders_vdf`
- `OS.workingpathstyle`
- `OS.steamlibpathstyle`
- `steamlib[].game`
- `game[].mods_found`
- `dommod[].mixed_id`

## 禁用历史名
- `islbfdvdflocate`
- `islbfvdflocate`
- `appitemid`
- `itemid`（若表示 mod 列表）

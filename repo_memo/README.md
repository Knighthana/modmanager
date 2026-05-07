# repo_memo

本目录是当前阶段的工作指挥与契约冻结区。

## 目标
- 将实现指挥从 `description/` 迁移到 `repo_memo/`
- 固化术语、字段命名与扫描流程
- 为后续实现和测试修复提供唯一参考

## 使用顺序
1. 先读 `TERMINOLOGY.md`
2. 再读 `STEAM_DISCOVERY.md`
3. 再读 `DATABASE_FIELDS.md`
4. 按 `IMPLEMENTATION_BRIEF.md` 执行

## 同步规则
- `description/` 仅作为用户与 Plan 的沟通目录，不作为 implement 默认输入
- 当前实现与契约以 `repo_memo/` 为准
- `json.example` 采用单向同步：`repo_memo/` -> `description/`
- implement 禁止将 `description/` 反向写回 `repo_memo/`

## 角色职责矩阵

| 角色 | description | repo_memo | repo_logs | work_memo |
|---|---|---|---|---|
| user | 读/写 | 可读 | 不使用 | 不使用 |
| plan | 读/写 | 读/写（主维护） | 不主动阅读 | 不主动阅读 |
| implement | 默认忽略；仅在 Plan 明确任务下写入 | 必读（实现指导） | 不主动阅读 | 读/写（states.md 状态维护） |

## 工作日志约定

### repo_logs/ — 冷备份日志
- 存放格式为 `YYYY-MM-DD.md` 的工作日志
- 内容：完成的变更摘要、关键决策、TODO 消化情况
- **不主动阅读，不占用注意力**——仅供历史追溯

### work_memo/ — 工作现场状态
- **唯一用途**：存放 `states.md`，记录当前 TODO / FINISHED
- 不作其他用途

### 日志录入流程
当提示"记录今日工作日志"时：
1. 读取 `work_memo/states.md` 中的 FINISHED 条目
2. 写入 `repo_logs/YYYY-MM-DD.md`
3. 从 `states.md` 清除已记录条目，保留 TODO

## 执行门禁
1. 实现任务必须引用本目录中的文档路径；缺失路径视为无效任务单。
2. 实现阶段不得以 `description/` 推导新规则，只可根据 `repo_memo/` 与 Plan 指令执行。
3. 涉及字段命名变更时，必须先更新 `TERMINOLOGY.md` 与 `DATABASE_FIELDS.md`，再改 `src/` 与 `tests/`。
4. 若 `repo_memo/` 与 `description/` 冲突，以 `repo_memo/` 为准，并将差异记录到 `MEMORY_SYNC_INDEX.md`。

## 违规后果
1. 发现以 `description/` 作为实现依据的提交，直接判定为无效实现，必须回滚并重做。
2. 未先更新契约文档即修改字段名的提交，禁止合并，需补齐文档与测试后重新评审。
3. 未记录冲突差异的提交，视为流程不合规，状态板降级为 blocked。

## Plan 授权例外流程
1. 仅当 Plan 明确写出例外范围时，允许临时引用 `description/` 作为补充背景。
2. 例外任务必须在任务单中写明：授权来源、有效期、影响字段、回收动作。
3. 例外结束后，必须在 `MEMORY_SYNC_INDEX.md` 追加回收记录；未回收前不得进入下一阶段。

## Replace-only 接口边界
1. 替换接口只做"替换执行"这一件事，不负责备份绑定、凭证校验、配置解析。
2. 替换接口输入必须是上游已决议的映射结果；若存在历史映射影响，需由上游先决议"当前有效源"。
3. 本阶段允许在 M1 之外实现 replace_service，后续可并入 M1。

## backup_dir 解耦边界
1. `backup_ops` 仅消费并校验传入的目录字符串，不负责目录命名规则生成。
2. 目录字符串生成由独立 builder 模块负责（prefix + id + updatetimehex + 可选路径拼接）。
3. `bakprefix`/`bakignore` 归属上游编排与构建层，不在 `backup_ops` 内硬编码。

## Plan 检查契约
1. Plan 接到检查需求、文档核验或疑似执行异常时，可查阅 `work_memo/states.md` 获取当前工作现场状态。
2. `work_memo/` 仅提供排障上下文，不作为契约裁决依据；契约冲突仍以 `repo_memo/` 为准。
3. `repo_logs/` 中的历史日志不参与任何检查或裁决流程。

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

# 引擎核心不变量

> Status: stable
> Authority: authoritative
> Read-Tier: always
> Purpose: 冻结引擎输出与运行时必须满足的不变量，作为 engine 修改的硬约束
> 更新：2026-05-09 — 新增扫描器错误码 E_DUPLICATE_APPID / E_DUPLICATE_MIXED_ID

> 来源：repo_logs/2026-04-21_M1_EXECUTION_CONTRACT.md，经 P0 后更新

## 数据结构不变量
- `mixed_id` 格式：`appid:modid`（colon-separated）
- `hashtype`：正常值为 `sha256`；计算前哨兵值为 `invalid`（表示尚未计算，不得视为合法哈希）
- final_mapping 只允许单文件到单文件，不允许通配符残留
- `changerequest` 中的 `action` **不允许出现 `hold`**；若出现说明聚合器或引擎流水线存在 bug，应断言失败而非静默通过

## 行为不变量
- 文件级环检测：基于具体文件链路，mod 级依赖环不直接判错；检测到环时产生告警 `W_FOREST_CYCLE_DETECTED`
- 森林允许分枝，分枝需告警（`W_FOREST_BRANCHING`）并等待用户决策
- 同输入同输出（确定性）

## 路径约定
- workingpathstyle 与 steamlibpathstyle 不一致时，先统一路径风格再参与计算
- 目录路径必须以 / 结尾，文件路径不得以 / 结尾（path_resolver 门禁）

## 告警码清单（引擎产生）
- `W_FOREST_BRANCHING` — 某路径存在多个候选来源，需用户裁决
- `W_FOREST_CYCLE_DETECTED` — 引用关系中检测到环，使用原始排序回退
- `W_SOURCE_DELETED` — 操作的源路径已被 delete 树标记为删除，本操作跳过
- `W_INVALID_ACTION` — action 字段值不在合法集合中，跳过
- `W_DESTIN_NONE_SKIPPED` — destin 为 none，操作跳过
- `W_MISSING_DEST_ROOT` — 目标 mixed_id 找不到对应 modpath，跳过
- `W_MISSING_INTO` — into 列表缺失或为空，跳过
- `W_MISSING_FROM` — from 列表缺失或为空（非 delete），跳过

## 错误码清单（扫描器 / 数据库产生）

以下错误码由 `database_ops.py` 在扫描过程中产生，非引擎产生：

- `E_DUPLICATE_APPID` — 同一 appid 在多个 Steam 库中被发现，存在重复的 game 条目。用户必须通过 `managed` 标记解决冲突
- `E_DUPLICATE_MIXED_ID` — 同一 mixed_id（appid:modid）在数据库中存在多个条目。用户必须通过 `managed` 标记解决冲突

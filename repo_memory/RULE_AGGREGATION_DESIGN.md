# Rule Aggregation Design

## 目标
在不改 M1 的前提下，定义 `kmm_rule_*.json` 的聚合流程，输出可执行规则与可追踪侧车数据。

## 输入
- 多个 `kmm_rule_*.json`
- 可选聚合配置（过滤、合并策略、冲突策略）

## 单文件格式约定
1. 主体结构可与 `aggregated_rule_set` 对齐。
2. 头部新增 `rule_meta_tag` 对象。
3. `rule_meta_tag` 至少包含：
   - `mainauthor`（允许空）
   - `author`（list，允许空）
   - `rulename`（允许空）

## 空值归一化
- `mainauthor` 为空 -> `anonymousauthor`
- `rulename` 为空 -> `unknownrulename`
- `actionorder` 可为空

## 聚合输出
1. `aggregated_rule_set`
   - 供 M1 直接消费，不引入额外执行耦合。
2. `source_trace_map`（sidecar）
   - 记录 action 来源信息：`mainauthor`、`rulename`、`actionorder`、来源规则文件。
   - 通过稳定键关联（例如 target/source/mixed_id/action 索引）。

## 性能策略
- 聚合阶段一次遍历同时产出 `aggregated_rule_set` 与 `source_trace_map`。
- 避免为生成 trace 再做一轮完整映射计算。

## 冲突与回退
- `actionorder` 仅作辅助。
- 相等、为空、不可判定、或用户要求手动时，一律回退人工拍板。

## 与 M1 的边界
- 当前阶段：M1 不改，M1 仍只接收 `aggregated_rule_set`。
- 未来阶段：可将 `action_meta_tag` 传导能力并入 M1。

## aggregated_rule_set 归一化补充（2026-04-22）
1. 聚合层输出的 action 中，`from` 与 `into` 统一归一化为 `list[string]`。
2. 对于非 `hold` 且非 `delete` 的 action，聚合层必须保留显式的 `from_type` 与 `into_type`；缺失不得猜测修复。
3. 对于 `delete`，聚合层只需保证 `into` 与 `into_type` 可用；`from` 与 `from_type` 可以缺省，也可以原样保留但下游忽略。
4. 对于最终解析为 `hold` 的 action，聚合层不需要为其补齐类型字段，因为执行层会直接跳过。

## action 继承规则补充（2026-04-22）
1. `def_action` 只作为子 action 缺省 `action` 的默认值。
2. 若子 action 显式声明了 `action`，则永远以子 action 为准，不再受父级 `def_action` 覆盖。
3. 因此 `def_action=hold` 只会让“未显式写 action 的子条目”变成 skipped action，不会吞掉显式的 `replace`、`create`、`delete`、`rename_then_replace`、`clear_then_copy`。

## 非法规则处理原则（2026-04-22）
1. 聚合层不负责把 path/file 混乱写法“修正成能跑”。
2. `into_type=file` 且 `from_type=path` 直接失败。
3. 若 `_type=path`，对应列表项必须全部以 `/` 结尾；否则直接失败。
4. 若单条 action 的 `from` 为多值或含 glob，同时 `into` 也为多值，直接失败。
5. 非法输入以 fail-fast 为准，不生成带猜测语义的 `aggregated_rule_set`。

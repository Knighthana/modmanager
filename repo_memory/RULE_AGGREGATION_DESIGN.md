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

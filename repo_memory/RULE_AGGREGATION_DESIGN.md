# Rule Aggregation Design

## 目标
在不改 M1 的前提下，定义 `kmm_rule_*.json` 的聚合流程，输出可执行规则与可追踪侧车数据。

## 输入
- 多个 `kmm_rule_*.json`
- 本地 `user_config.json`（读取 `path_alias`、`path_handle`、`path_target`）
- 可选聚合配置（过滤、合并策略、冲突策略）

## 单文件格式约定
1. 主体结构可与 `aggregated_rule_set` 对齐。
2. 头部新增 `rule_meta_tag` 对象。
3. `rule_meta_tag` 至少包含：
   - `rulenamespace`（允许空）
   - `author`（list，允许空）
   - `rulename`（允许空）

## 空值归一化
- `rulenamespace` 为空 -> `anonymousnamespace`
- `rulename` 为空 -> `unknownrulename`
- `provenance_ref` 缺失或空值 -> `404` + warning
- `sidecar_ref` 缺失或空值 -> `404` + warning
- `action_order` 默认值为 `0`

## 聚合输出
1. `aggregated_rule_set`
   - 供 M1 直接消费，不引入额外执行耦合。
2. `source_trace_map`（sidecar）
   - 记录 action 来源信息：`rulenamespace`、`rulename`、`provenance_ref`、`action_order`、`sidecar_ref`。
   - 通过稳定键关联（例如 target/source/mixed_id/action 索引）。

## 动作级追踪模型
1. 动作级只使用 `provenance_ref`、`action_order`、`sidecar_ref`。
2. `provenance_ref` 的格式固定为 `path_handle:relative_path`。
3. 聚合层解析 `provenance_ref` 时必须基于 `user_config.path_alias` 做 `realpath` 归一化与前缀校验，禁止目录穿越。
4. `action_order` 由聚合器或 GUI 在运行时注入，类型必须为 int；默认值为 `0`，不做猜测。

## 性能策略
- 聚合阶段一次遍历同时产出 `aggregated_rule_set` 与 `source_trace_map`。
- 避免为生成 trace 再做一轮完整映射计算。

## 冲突与回退
- `action_order` 仅作辅助，不作为规则正确性的兜底来源。
- 命中过程冲突且双方 `action_order` 相等，或任一方 `action_order=0` 时，直接抛错。
- 用户若坚持使用冲突规则与手动优先级，风险由用户自行承担。

## delete 捋枝规则
1. 先建树，再捋枝。
2. 同一 rule 内对同一目标文件的连续操作，按 actionlist 顺序串成同一枝。
3. delete 请求不携带可继续命中的 source path，因此在当前 forest 模型中只能作为叶请求存在。
4. 命中 delete 叶时，在树生成后的决议阶段将其折叠提升为对根 target 的删除请求。
5. 执行阶段删除 `final_mapping.path` 对应文件；当前规范不采用“子节点提升并重挂祖父”的树重写语义。

## 与 M1 的边界
- 当前阶段：M1 不改，M1 仍只接收 `aggregated_rule_set`。
- 未来阶段：可将 `provenance_ref`、`action_order`、`sidecar_ref` 传导能力并入 M1。

## aggregated_rule_set 归一化补充（2026-04-22）
1. 聚合层输出的 action 中，`from` 与 `into` 统一归一化为 `list[string]`。
2. 对于非 `hold` 且非 `delete` 的 action，聚合层必须保留显式的 `from_type` 与 `into_type`；缺失不得猜测修复。
3. 对于 `delete`，聚合层只需保证 `into` 与 `into_type` 可用；`from` 与 `from_type` 可以缺省，也可以原样保留但下游忽略。
4. 对于最终解析为 `hold` 的 action，聚合层不需要为其补齐类型字段，因为执行层会直接跳过。
5. `def_destin` 与 action 级 `destin` 允许值为 `appid:modid` 或 `none`。
6. `destin=none` 仅表示保留/占位目标；若 action 最终不是 `hold`，执行层必须记录 warning 并跳过该 action。

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
6. 聚合层不引入 `file_and_path` 之类的混合类型，也不把 `from_type=file` 的 glob 自动扩成“文件+目录一起处理”。
7. 若规则作者想表达 `cp -r src/* dest/` 的效果，必须显式拆成“目录 action”与“文件 action”两条规则，而不是依赖单条混合语义。

# Open Conflicts (Unresolved)

来源：/memories/session/conflict_analysis.md
更新时间：2026-04-21

仅保留当前仍需决策的冲突。

## 1. 路径风格转换时机与层级
- 冲突：workingpathstyle 与 steamlibpathstyle 不一致时，转换在发现层、解析层还是映射层执行。
- 风险：重复转换导致路径错配。
- 结论（2026-04-21）：已决策为“进入 backup/apply/restore 边界后立即规范化”。
- 状态：closed。

## 2. hash 占位与合法值边界
- 冲突：示例允许 invalid/0 占位，但执行约束强调 sha256。
- 风险：校验口径不一致导致运行期拒绝合法占位状态。
- 结论（2026-04-21）：两阶段校验策略。
  - **写入阶段**（`_check_filefoldertree_transition`）：只检查"不倒退"，即 `hashtype` 不得从非-invalid 倒回 invalid，`hashvalue` 不得从非-0 倒回 0。写入时允许保留 `invalid/0` 占位初始状态，不拒绝。
  - **展示/读取阶段**（M4 UI 层）：按状态机渲染。`hashtype=invalid` + `hashvalue=0` 显示为"未计算"；`hashtype=sha256` + `hashvalue=<64位hex>` 显示为"已计算"。
  - 合法状态集：`{invalid, 0}` 为初始占位，`{sha256, <hex>}` 为终态，不存在中间混合态。
- 实现验证（2026-04-21）：`engine._check_filefoldertree_transition` 行为已符合两阶段写入约束，无需修改。
- 状态：closed。

## 3. filefoldertree 的"结构冻结 vs 属性单向演进"边界
- 冲突：文案同时出现"不可修改"与"允许三字段单向修改"。
- 风险：实现层无法统一权限判断。
- 结论（2026-04-21）：
  - **结构冻结**：节点创建后，名称、类型、父子关系、子节点列表均不可变更。任何试图修改结构的操作必须被拒绝并报错（`E_TREE_NODE_MUTATION` / `E_TREE_STRUCTURE_MUTATION`）。
  - **属性单向演进**：仅 `file` 节点的 `isbackuped`、`hashtype`、`hashvalue` 三字段允许单向变更一次，方向固定为：`false→true`、`invalid→sha256`、`0→<hex>`。反向修改报 `E_TREE_ATTR_BACKWARD`。
  - `folder` 节点的上述三字段不适用单向演进（folder 不备份）。
- 实现验证（2026-04-21）：`engine._check_filefoldertree_transition` 行为已完全符合上述措辞，无需修改。
- 状态：closed。

## 4. backup 与 filemap 的执行时序
- 冲突：备份依赖完整 filemap，但替换前又要求已有可用备份树。
- 风险：用户流程出现门禁冲突。
- 结论（2026-04-21）：统一时序为“计算 -> 建树备份 -> 替换 -> 恢复/冲突治理”。
- 状态：closed。

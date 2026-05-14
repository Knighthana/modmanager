# GUI 稳定化实施清单（Implement 可执行版）

## 目标
- 先止血高优先级 GUI 问题，再统一状态流与页面职责。
- 每阶段独立提交，保证可回滚。

## 阶段 1（P0）功能契约修复
1. 修复扫描模式语义：确保“仅自动/全部/仅手动”对后端参数映射正确。
2. 修复 compute 参数契约：统一使用 aggregated_rule_set。
3. 修复计算结果统计显示：避免“0 棵树 0 映射”假成功。
4. 修复 ForestPage 职责越界：不再直接触发计算与运行。

## 阶段 2（P0/P1）状态流统一
1. 明确 workspace 单一写入口。
2. SettingsPage 在 database rename/delete 时同步迁移或清理 perDatabase 数据。
3. 聚合规则恢复链路统一为：内存 -> aggregatedRuleMeta.output_path -> 提示重聚合。

## 阶段 3（P1）刷新一致性
1. 统一 AdvancedPage 三个标签的自动刷新策略。
2. 统一手动刷新与自动刷新的优先级与触发时机。

## 阶段 4（P1）视觉一致性收敛
1. 统一标题布局、按钮尺寸、表格行高、区块间距。
2. 输出可复用样式约束，逐页替换落地。

## 阶段 5（P1）文档冻结同步
1. 更新 DESIGN_GUI.md（页面职责、刷新策略）。
2. 更新 DESIGN_GUI_WORKSPACE.md（workspace 数据流与恢复顺序）。
3. 更新 DESIGN_REST_API.md（端点参数与响应示例）。
4. 更新 TERMS_FIELD_FREEZE.md（字段冻结）。

## 验收门禁
1. 扫描模式行为可区分且与文档一致。
2. compute 完成后计数显示正确。
3. ForestPage 仅消费结果，不触发计算。
4. AdvancedPage 三标签刷新行为一致。
5. 前端测试与构建通过。
6. 每阶段都有独立 commit，可单独回滚。

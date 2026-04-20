# Engineering Patterns

来源：/memories/patterns.md
更新时间：2026-04-21

## 稳定模式
1. 跨平台路径作为键前，先做规范化并折叠重复分隔符。
2. 工具模块必须进入生产主流程，避免只在测试里可用。
3. compute_mapping 输入校验顺序固定：
   - validate_config
   - validate_database
   - validate_branch_decisions
   首错即停。
4. 新增更严格校验时，必须同步更新既有测试夹具，避免回归假失败。

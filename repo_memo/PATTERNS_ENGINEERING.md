# Engineering Patterns

来源：/memories/patterns.md
更新时间：2026-05-06

## 稳定模式
1. 跨平台路径作为键前，先做规范化并折叠重复分隔符。
2. 工具模块必须进入生产主流程，避免只在测试里可用。
3. compute_mapping 输入校验顺序固定：
   - validate_aggregated_rule_set
   - validate_database
   - validate_branch_decisions
   首错即停。
4. 新增更严格校验时，必须同步更新既有测试夹具，避免回归假失败。

## 新增模式（P0 森林模型重构后）
5. 森林以独立根树构建，树间通过引用（refs）表达依赖，不做刨根移栽。
6. 解析方向：自底向上（被引用者先于引用者），拓扑排序驱动。
7. delete 语义：限于自身树根，不向上传播。引用者通过祖先检查判断源可用性。
8. 输出契约：`compute_mapping` 返回 `trees`（非 `forest`），`final_mapping` 格式不变。
9. 分岔裁决：单操作树自动裁决，多操作树标记 pending 等待决策。
10. 文档先行：架构级改动必须先在 repo_memo/ 产出设计文档，再改代码。

## 开发环境约束

- **Python / pip**：所有 Python 操作（安装依赖、运行测试、启动服务）必须在项目根目录的 `.venv/` 虚拟环境中执行。禁止向系统 Python 或其他虚拟环境安装包。
- **Node / npm**：所有 Node 操作必须通过本机安装的 `fnm` 管理的 Node 版本执行。版本固定见项目根目录 `.node-version`，进入目录后 fnm 自动切换。禁止绕过 fnm 直接调用系统 node/npm。

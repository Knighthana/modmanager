# 2026-05-14 工作日志（审计前）

## 讨论裁定

- 方案 B 终版：workspace.json 撤销，用户决策存前端 localStorage
- databases 对象替代 database_output_path + custom_databases
- per_database 嵌套结构 → 扁平 + database_name 标记 → 最终方案 B（无 backend workspace）
- managedEntries / branchDecisions 归属前端 localStorage
- 下拉组件的 database_name? 操作参数（临时覆盖），不写 user_config
- aggregator 不接收 user_config_path
- ~ 展开归 path_resolver

## Phase 1 — 数据层
- bootstrap.py: user_config 单级搜索 + first_use
- bootstrap.py: generate_database 删除 cache_path，使用 databases[name].path
- rule_aggregator.py: 删除 user_config_path 参数
- orchestrator.py: 签名确认 managed_entries 参数

## Phase 2 — API 层
- schemas.py: 删除 workspace schema，所有请求体加 database_name
- routes/workspace.py: 删除
- routes/database.py: generate/read/save 改为 database_name
- routes/pipeline.py: compute/run 使用 database_name + managedEntries + branchDecisions
- routes/rules.py: aggregate 不从 workspace 读路径
- routes/config.py: save 删除 output_path

## Phase 3 — 前端重构
- DatabaseSelector.vue: 公共下拉组件
- 各 store: 删除 databasePath/databaseJson/userConfigPath/cachePath
- 各页面: 加 DatabaseSelector、删 workspace API 调用
- localStorage: 聚合为单一 modmanager:workspace key

## Phase 4 — 自动恢复 + 缓存修正
- bootstrap.py: manual 模式跳过缓存（db_file 定义外提）
- DataSourcePage/AdvancedPage/ForestPage: onMounted 自动调 /api/database/read
- delete workspace.py 残留 + pipeline.py 删 user_config_path=""
- test_workspace.py 删除

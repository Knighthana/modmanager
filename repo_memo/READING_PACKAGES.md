# READING_PACKAGES — Tier 1 阅读包索引

> Status: stable
> Authority: authoritative
> Read-Tier: always
> Purpose: 将 Tier 1 设计文档压缩为少量任务包，减少默认上下文膨胀

## 使用规则
- 每轮任务先选一个阅读包，再读包内文档
- 默认只选 1 个包；确需跨域时最多 2 个包
- 包外文档只在明确需要时追加，不作为默认输入

## 包契约
- 每个包都必须说明适用范围和排除范围
- 每个包默认最多读取 3 份文档；超过时先缩小任务或拆分子任务
- 跨包读取必须说明原因，并优先选择共同依赖最少的包
- 包内文档只提供默认入口，不替代具体任务的最小读集判断

## 包 A1：采集与规则

适用：database、规则聚合、森林模型。

排除：编排、备份、路径解析、REST API、GUI 页面实现。

- [DESIGN_STEAM_DISCOVERY.md](DESIGN_STEAM_DISCOVERY.md)
- [DESIGN_RULE_AGGREGATOR.md](DESIGN_RULE_AGGREGATOR.md)
- [DESIGN_FOREST_MODEL.md](DESIGN_FOREST_MODEL.md)

## 包 A2：运行编排

适用：编排、备份、路径解析。

排除：采集聚合、REST API、GUI 页面实现、前端集成细节。

- [DESIGN_ORCHESTRATOR.md](DESIGN_ORCHESTRATOR.md)
- [DESIGN_BACKUP.md](DESIGN_BACKUP.md)
- [DESIGN_PATH_RESOLVER.md](DESIGN_PATH_RESOLVER.md)

## 包 A3：API 与执行约束

适用：REST API、引擎约束、Python 分层约束。

排除：采集聚合、备份与路径解析实现细节、GUI 页面实现。

- [DESIGN_REST_API.md](DESIGN_REST_API.md)
- [DESIGN_ENGINE_INVARIANTS.md](DESIGN_ENGINE_INVARIANTS.md)
- [DESIGN_PYTHON_LAYERS.md](DESIGN_PYTHON_LAYERS.md)

## 包 B1：GUI 核心

适用：GUI 总体、数据源、计算准备。

排除：任务流协议、前端集成细节、Mock 基础设施。

- [DESIGN_GUI.md](DESIGN_GUI.md)
- [DESIGN_GUI_DATASOURCE_TAB.md](DESIGN_GUI_DATASOURCE_TAB.md)
- [DESIGN_COMPUTE_PREP_PAGE.md](DESIGN_COMPUTE_PREP_PAGE.md)

## 包 B2：GUI 流程与集成

适用：GUI 任务流、前端第三方集成、Mock 基础设施。

排除：GUI 总体布局、数据源页细节、计算准备主流程。

- [DESIGN_GUI_EXECUTION_PROTOCOL.md](DESIGN_GUI_EXECUTION_PROTOCOL.md)
- [FRONTEND_INTEGRATION_CONSTRAINTS.md](FRONTEND_INTEGRATION_CONSTRAINTS.md)
- [DESIGN_MOCK_INFRA.md](DESIGN_MOCK_INFRA.md)

## 包外原则
- `README.md`、`DOCUMENT_GOVERNANCE.md`、`DOCUMENT_METADATA.md`、`PATTERNS_ENGINEERING.md`、术语冻结文档，仍归 Tier 0
- 历史归档、迁移记录、审计说明默认不读，按需进入 `repo_logs/`

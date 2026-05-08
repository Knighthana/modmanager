# Process Description (repo_memo authoritative)

> Status: stable
> Authority: authoritative
> Read-Tier: always
> Purpose: 提供系统主流程、模块分工与当前阶段总览，作为跨模块任务的总览入口
> Supersedes: `description/process_description.md`

这是当前阶段的执行总览文档，用于替代 `description/process_description.md` 的指挥作用。

## 业务目标
- 基于 Steam 库与工坊文件建立可计算的映射关系
- 对改动进行可追溯备份与恢复
- 在跨平台路径环境（Windows/Linux/WSL）下保持一致行为

## Discovery Pipeline
1. 定位候选 `steamapps` 路径
2. 标记 `contains_libraryfolders_vdf=true` 的主发现点
3. 解析主 `libraryfolders.vdf` 扩展全部库路径
4. 遍历每个库解析 `appmanifest_*.acf`
5. 默认仅对 `steamlib[].game` 范围内 appid 解析 `appworkshop_*.acf`
6. 生成 `database` 结构并保存
7. 自动发现失败时，必须回退到手动指定库路径并继续流程

## 数据维护流程
1. 永远允许用户手动维护 `steamlib`（CRUD）
2. `liveupdate`：按 `steamlib` 变化增量刷新 `game` / `dommod`
3. `regen`：清空 `game` / `dommod` 后按最新 `steamlib` 全量重建
4. 仅当无可用工作目录时提示用户介入

## 数据契约分工
- 术语冻结：`TERMS_TERMINOLOGY.md`
- 扫描契约：`DESIGN_STEAM_DISCOVERY.md`
- 字段冻结：`TERMS_FIELD_FREEZE.md`
- 字段定义：`repo_spec/database.schema.json`
- 示例数据：`*.example`
- 工程约束：`PATTERNS_ENGINEERING.md`
- 执行指令：`DOCUMENT_GOVERNANCE.md`

## 关键约束
- 单概念单字段名，禁止历史别名继续落库
- 文档先于实现：先冻结契约，再改代码
- 测试必须覆盖跨盘库发现，不允许仅验证默认安装位置

## 映射计算流程（P0 更新）
1. 聚合器：多份 kmm_rule → `aggregated_rule_set`（含 `def_destin`/`def_action` 具体化 + 鉴权）
2. 引擎：`compute_mapping()` 展开 actionlist → 构建 ForestTree（独立根+引用）→ 拓扑排序 → 自底向上解析 → 输出 `trees` + `final_mapping`
3. 可视化：`forest_visual.py` 将 trees 渲染为 ASCII/DOT/SVG/HTML
4. 备份：`backup_dir_builder` 自动推导 backup_dir 命名 → `backup_ops` 执行差异备份
5. 替换：`apply_final_mapping()` 将 final_mapping 写入磁盘

## 当前阶段状态
- Phase P0: 森林模型重构 ✅（独立根+引用，trees 输出）
- Phase P1: Backup 实现 ✅（builder + 循环防护）
- Phase P2: 引擎细节修复 ✅（delete→create warning + 术语统一）
- Phase P3: GUI 增强 ✅（全部/仅分岔 + hover 高亮 + 点击选枝）
- 全量测试：Python 322 + 前端 18 全部通过

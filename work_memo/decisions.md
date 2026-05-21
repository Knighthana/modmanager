# 当前决策记录

> 本文件由 arch 维护。只记录当前有效的架构原则。
> 已完成的施工决策见 `repo_logs/2026-05-21.md`。

## 架构原则（active）

- **P1**: Orchestrator 为星形拓扑核心，唯一入口 `dispatch()`——Web / CLI 全部通过它调度
- **P2**: 文件操作四层模型——Entry（`TaskRequest`）→ Resolver（`CleanContext`）→ Planner（`FileOpsPlan`）→ Primitive（`*_ops.py`）
- **P3**: Planner 按 `intent` 自主决定 preflight：apply/restore 必须，run 豁免，backup 不需要
- **P4**: 原语严格 file-to-file，运行时 `_assert_is_file()` 拒绝目录
- **P5**: `.kmmignore`（gitignore 语法）由 Planner 统一收集，对所有操作生效
- **P6**: `backupinfo.tree` 为源目录完整结构镜像，`isbackuped` 对照 backup_dir 标记
- **P7**: 不采用状态机——`dispatch` + phase 序列足够
- **P8**: `compute` 管线独立文件，逻辑暂不动；`DESIGN_MIGRATION_LAYERS.md` 定义 Rust 迁移分层
- **P9**: `prep` 原语独立——创建 backup_dir + 建初始 tree + 写 `backupinfo.json`；Planner 决定是否需要建树；backup/restore/apply 彻底不接触 ignore

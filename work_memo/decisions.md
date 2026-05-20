# 当前决策记录

> 本文件由 arch 维护，smith 在每次任务前检查 L1 约束是否与既有决策冲突。
> 本文件不是契约权威来源；若与 `repo_memo/` 冲突，以 `repo_memo/` 为准。

## 2026-05-20 术语与接口清退

### 已确认决策

- **D1**: 删除整个 `cli-hmi/` 目录，同时清理所有外部文档中的 `cli-hmi` 路径引用
- **D2**: `engine.py` 中 `_check_dir_tree_transition()` 移除 `"directory"` → `"dir"` 向后兼容代码，强制仅接受 `"dir"`
- **D3**: `tests/test_orchestrator.py:352` `"kmmbackup_"` → `"kmmbackup"`（非违例测试，属旧值残留）
- **D4**: 前端 `RulesOverviewPage.vue`：`rulenamespace` 空时回退 `"anonymousnamespace"`，`rulename` 空时回退 `"unknownrulename"`（不再回退到 `file.name`）
- **D5**: 全仓库文档中清除 `appitemid`、`dommod`、`islbfdvdflocate` 三个历史别名的所有出现
- **D6**: `engine.py` 私有 dataclass `ForestTree` 不重命名
- **D7**: 警告码 `W_FOREST_BRANCHING` 不重命名（报错是给人看的）
- **D8**: `description/` 目录下的示例文件由用户自行修改，仅提供修改建议；与 D5 冲突时 D8 优先（即 `description/database.json.example` 由 arch 输出建议，smith 不直接编辑）

- **D9**: `repo_spec/` schema 补全与字段统一施工——新增 9 个 schema + 修改 10 个既有 schema（原禁区"不修改 schema 文件 / repo_spec JSON"已由 user 直接指令覆盖，开发阶段无生产数据）

## 2026-05-21 架构重构 — Orchestrator 四层模型

### 已确认决策

- **D10**: Orchestrator 采用 Entry → Resolver → Planner → Primitive 四层模型
- **D11**: Entry 层只拼装 `TaskRequest` object，不做语义解析；`resolver_args` 为 opaque dict，语义由 Resolver 自决
- **D12**: Resolver 只收集「资源」（database / mapping / user_config 等磁盘文件内容），不读取「状态」（backupinfo）——backupinfo 由 Planner 或其 helper 负责
- **D13**: Planner 根据 `intent` 自主决策是否做 preflight：apply / restore 必须做，run 豁免（backup 紧耦合 apply），backup 不需要；preflight 用 enum 分支
- **D14**: 备份/应用/恢复三大原语各自独立为 `*_ops.py`（`backup_ops.py`、`apply_ops.py`、`restore_ops.py`），`run` 为组合原语
- **D15**: 所有原语严格 file-to-file，删除全部目录处理代码（`rmtree` / `copytree` 等）
- **D16**: Orchestrator 是唯一入口，Web API 和 CLI 全部通过它调度，内部细节零对外暴露
- **D17**: 不采用状态机——Orchestrator 核心为 dispatch + phase 序列
- **D18**: `compute` 管线单独拆到 `orchestrator/compute_pipeline.py`，只搬不改逻辑
- **D19**: `preflight` 为 `orchestrator/preflight.py` 单文件
- **D20**: `.kmmbakignore` 语义保留为 backup 专属，不改名，不扩展到 apply/restore
- **D21**: 实施顺序为「先建新文件，再改调用方，最后删旧代码」——避免中间态不可构建

### 禁区

- 不跑测试

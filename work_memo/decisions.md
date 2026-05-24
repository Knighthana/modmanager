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
- **P10**: `bakignore` 独立于 `kmmignore`——bakignore 联动 `baksuffix` 自动维护，仅 backup 生效；kmmignore 由用户手写，gitignore-parser 匹配，全部操作生效
- **P11**: 规则文件预检漏斗（两层）——`rule_validator.py`（Schema 粗筛）+ `path_normalizer.py`（语义精筛），在聚合器入口前执行
- **P12**: bootstrap 职责收缩——只负责环境探测和引导；user_config 的创建/补全/修复外包给 `user_config_init.py`
- **P13**: `source_path` 是 bootstrap 入参兼出参（传入→优先使用；不传→平台默认找；返回生效路径），**不**持久化在 `user_config` 内部
- **P14**: `first_use` 删除——调用方自行判断"文件是否由我首次创建"
- **P15**: `rule_sources` 改为 `{name: {paths: [...]}}` 对象套对象——与 `databases` 一致；前端只传名字，后端解析路径
- **P16**: `workspace_dir` 首次创建时按平台填入默认值并固化到 `user_config`；运行时以 `user_config.workspace_dir` 为准，不执行平台回退
- **P17**: `backupinfo.snapshot_time` 拆为 `tree_created_time`（首次建树时刻，prep 写一次）+ `last_modified_time`（每次增量更新）——原 `snapshot_time` 废弃
- **P18**: `PipelineResult` 所有非空 `*_result` 必须含 `"dry_run": bool`——`__post_init__` 运行时报错；适配器必须提取
- **P19**: `dry_run=True` 禁止一切磁盘写操作——prep 阶段的 `os.makedirs` + `backupinfo.json` 写入在 `_dispatch_fileops` 中受 `not plan.dry_run` 守卫
- **P20**: 树节点 hash 字段统一为 `hashtype` / `hashvalue`（扁平键名），禁用 `type` / `value` 或 `hash.type` / `hash.value` 写法
- **P21**: bootstrap 职责收缩为"环境探测 + 校验"——不写文件，不创建目录，不生成数据库；`discover_user_config` 拆分三步：
  - bootstrap 读取文件 → 判断 complete/合法 → 发现不完整则调 `userconfig_init(path)` 补全
  - `userconfig_init` 只补空值键（以 schema `required` 为准），不覆盖已有值；若值非法则退回 bootstrap 报错
  - `userconfig_save(config_index, data)` 处理前端修改（编辑/保存），与 bootstrap 无关
  - **`config_index` 是 `discover_user_config()` 的必填参数**——调用方必须传入完整路径；bootstrap 不执行平台默认路径猜测
  - 平台默认路径（`workspace_dir`、`database`）由 `userconfig_ops._detect_platform_defaults()` 内部维护
- **P22**: `user_config.schema.json` 的 `required` 扩容为全部 9 个必填键（`schema_namespace`/`schema_version`/`baksuffix`/`kmmignore`/`bakignore`/`rule_sources`/`path_alias`/`workspace_dir`/`databases`），以保证"schema 认为 complete"与"业务需要 complete"一致

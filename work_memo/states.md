# 工作状态

> arch 维护。

## Schema/Code 对齐审计 — 待办

> 2026-05-23 schema vs 实现审计产出。按 Wave 划分。

### Wave 1 — 文档（4 条）

- [x] DOC-01 `DESIGN_BOOTSTRAP.md` §1.2
- [x] DOC-02 `DESIGN_BACKUP_OPS.md` 行66/101/183 — type/value → hashtype/hashvalue
- [x] DOC-03 `DESIGN_BACKUP_DIR.md` + `DESIGN_BACKUP_OPS.md` + `backupinfo.schema.json` — snapshot_time → tree_created_time + last_modified_time
- [x] DOC-04 `DESIGN_RULE_AGGREGATOR.md` — into_type required + from_type 参数说明

### Wave 2 — 基础设施（新模块 + Schema）

- [x] MOD-01 `path_normalizer.py` + tests
- [x] MOD-02 `rule_validator.py` + tests
- [x] MOD-03 `userconfig_ops.py` + tests
- [x] SCH-01 `backupinfo.schema.json` — 删多余 `version`；`schema_version` 改 const
- [x] SCH-02 `user_config.schema.json` — 加 `bakignore` 字段
- [x] SCH-03 `user_config.schema.json` — `rule_sources` 改为 `{name: {paths: [...]}}`
- [x] ~~SCH-04 `user_config.schema.json` — `required` 扩容为 9 键~~ → 已废弃：required 现为 6 键（`bakignore` 和 `path_alias` 不 required）

### Wave 3 — 核心修正

- [x] CORE-01 bootstrap 拆分（P21）
- [x] CORE-02 bakignore 联动 baksuffix
- [x] CORE-03 rule_sources name→paths 解析
- [x] CORE-04 恢复 `_flatten_tree_file_hashes()` + 补测试
- [x] CORE-05 修正 `_tree_node_status` + `W_BACKUP_NODE_NOT_IN_TREE`
- [x] CORE-06 `snapshot_time` → `tree_created_time` 迁移

### Wave 4 — 清扫

- [x] CLN-01 `_target_for` nwname→target_rel，删 from_type 参数
- [x] CLN-02 删除 aggregator 中 nwname 透传
- [x] CLN-03 `/config/save` → `userconfig_save`
- [x] CLN-04 `user_config.json.example` 补全默认字段
- [x] CLN-05 `DESIGN_PATH_CASE.md` P0 normalize_path() 实施

---

## 代码审计发现（2026-05-25）— 状态校准（2026-09-08 复核）

> 2026-09-08 逐项复核：全部已解决，本区块仅存档。

| # | 结论 |
|---|------|
| BUG-1 | 已解决 — `_list_orphans` 与其调用点均已随 restore 链路重构移除 |
| BUG-2 | 已解决 — `routes/pipeline.py` 已删除（裁定 9） |
| P11-GAP | 已解决 — `rule_aggregator.py:25` 调用 `normalize_rule_actions`；`rule_validator` 经 `orchestrator/verifier.py` 由 `modmgr_web/routes/workspace.py:185` 调用；`test_validator_normalizer_placement.py` 守护接线 |
| P12-GAP | 已解决 — 见 2026-06-03 DataPort 重构（generate_database 磁盘写入已按架构收口；如需再核对本条，读 `DESIGN_BOOTSTRAP.md`） |
| CODE-3 | 已解决 — `find_appmanifest_acf_files` / `find_appworkshop_acf_files` 已从 `acf_parser.py` 删除 |
| CODE-4 | 已解决 — `isinstance(rs, list)` 分支已不存在 |
| CODE-5 | 已解决 — `run_apply_preflight` / `run_restore_preflight` 的 `context` 参数已移除 |
| CODE-6 | 已解决 — bootstrap.py 无 `source_path` / `first_use` 残留 |
| CODE-7 | 已解决 — src 下无旧包名 `modmanager` 残留 |

---

## 实机失败化石收纳流程（2026-09-08 起）

> 背景：此前实机测试发现文件搬运不符合预期，但失败案例未记录而遗失。
> 纪律：任何一次实机测试中观察到的异常行为，都必须留下记录，并最终固化为夹具测试。

流程：
1. 实机发现异常 → 在 `user_memo/audit_logs/` 记录一份 field report（日期、操作序列、期望 vs 实际、环境：Windows/WSL2）；
2. 排期把该案例固化进沙盒测试矩阵（`tests/test_full_pipeline_integration.py` 生命周期场景模式）作为永久回归测试；
3. 固化完成后在 field report 上标记 `[fossilized: tests/xxx.py::test_yyy]`。

持续有效的 invariant：实机测试的每一小时痛苦都应兑换成至少一条自动测试。

---

## 当前进行中

- [x] (done) TASK2609-0x1 [arch] 全量文件操作 SPEC 审计 — 完成。产出：`user_memo/audit_logs/2026-09-08_fileops-spec-audit.md`（含裁决记录与执行结果）。要点：4 个 S 级实现 bug（bakignore 自匹配致备份静默空转并有一条测试固化该行为 / Planner 警告在管线层被吞 / CLI restore 必崩 / 多 backup_dir 时 prep 重扫违反 §7.2）、mod 内 .kmmignore 生产路径不生效、PATH_CASE P1-P3 未接线（normalize_path 零调用方）、错误码与 TERMS 大面积脱节
- [x] (done) TASK2609-0x3 [arch] 四波修复执行 — 完成，646 tests / 0 skip / 0 fail。五项裁决全部落地（bakignore 源侧语义、restore 显式 backup_dirs、工作区=组合+版本绑定命名、惰性保留、大小写只报告不改写）；详见审计文档"裁决记录与执行结果"。附带修复：cli.py 三处运行时必崩（缺 import / asdict / restore 推导崩溃）、RUN intent 无 prep 缺口、E_RESTORE_NOT_FILE 守卫、dry-run 保真
- [ ] (pending) TASK2609-0x2 [arch] 沙盒生命周期场景矩阵 — 以 `test_full_pipeline_integration.py` 为原型参数化：首次备份→应用 / 应用→恢复 / 换规则轮转 / kmmignore 跨轮次 / bakignore 交互 / 多库 / 非法规则输入；不变量：dry-run 零副作用、跨 MOD 零污染、目录树/backupinfo 树/hash 三方一致；期望值以 TASK2609-0x1 裁决后的行为为准
- [ ] (pending) TASK2609-0x4 [arch] PATH_CASE P1 入口归一化 — 前置条件：DESIGN_PATH_CASE §七注记（Windows 工作风格条款：POSIX 分支用 normalize_path，Windows 分支保分隔符仅做大小写归一）+ 混合大小写 Windows 路径测试夹具更新
- [ ] (pending) TASK2609-0x5 [arch] D3 裁决：backup 逐文件全量回写 backupinfo.json 在大树 + DrvFs 上为 O(N²) I/O，是否改为批量/时间窗回写（中断幂等性论证见审计文档 D3）

---

## 悬空待办

- [ ] (pending) TASK2605-0x1 [user] 前端空输入校验，“待后端端点均符合预期后再开展”
- [ ] (pending) TASK2605-0x2 [user] 统一界面视觉效果: 字体 按钮
- [ ] (pending) TASK2605-0x3 [user] 主题切换，根据日出日落/系统主题自动切换界面亮暗效果
- [ ] (pending) TASK2605-0x4 [user] 自动输出日志文件到规定位置整洁
- [ ] (pending) TASK2605-0x5 [user] 规则概览 — preview 图片加载；设计就绪（`DESIGN_EXT_RESOURCE.md`），待 `ext_resource` 包实现
- [ ] (pending) TASK2605-0x6 [user] 规则概览 — README 文件内容查看；同上
- [ ] (pending) TASK2605-0x7 [user] 规则概览 — author 字段的键含义与展示方式待讨论
- [x] TASK2605-0x9 [user] bootstrap 自动发现 + steam.exe 手动指定 + macOS 支持 + 三平台默认路径
- [ ] TASK2605-0xA [user] 路径大小写检查/模糊开关 → P0 `normalize_path()` 已完成；P1-P3 待推进
- [ ] TASK2605-0xB [user] 修 `DESIGN_STORAGE.md` 中过多硬编码默认值的问题

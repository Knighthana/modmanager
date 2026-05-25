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

## 代码审计发现 — 待修（2026-05-25）

### 🔴 紧急

| # | 位置 | 问题 |
|---|------|------|
| BUG-1 | `backup_ops.py:639` | `_list_orphans()` 被调用但从未定义 → `restore_from_backup` 孤儿检测崩溃 |
| BUG-2 | `routes/pipeline.py:107` | restore SSE 端点不转发 `on_progress` → 前端进度条永远不动 |

### 🟡 非紧急

| # | 位置 | 问题 |
|---|------|------|
| P11-GAP | `rule_validator.py` + `path_normalizer.py` | 模块存在但聚合器 `aggregate()` 未调用 |
| P12-GAP | `bootstrap.py` | `generate_database()` 仍在 bootstrap 中写磁盘，违反 P12 |
| P21-GAP | `decisions.md` P21 | 引用了不存在的函数名 `_detect_platform_defaults()`（实际在 `osplatform.py`） |
| P22-GAP | `decisions.md` P22 | 说 required 含 `bakignore`（7 键），实际 6 键（不含） |
| CODE-3 | `acf_parser.py` | `find_appmanifest_acf_files` / `find_appworkshop_acf_files` 零调用方 |
| CODE-4 | `routes/config.py:40` | `_normalize_rule_sources` 中 `isinstance(rs, list)` 分支永远不进 |
| CODE-5 | `preflight.py` | `run_apply_preflight` / `run_restore_preflight` 的 `context` 参数从未使用 |
| CODE-6 | `bootstrap.py:146-147` | 注释残留旧名 `source_path` / `first_use` |
| CODE-7 | `__init__.py` / `app.py` | 残留旧包名 `modmanager` |

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

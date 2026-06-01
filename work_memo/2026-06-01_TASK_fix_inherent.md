# Task-Card: 固有问题修复（裁定 2/3/4/6）

**目标**
修复与架构无关的代码缺陷和文档错误，清理完毕后做一次提交。

**L1 硬约束**
- [ ] 不涉及任何架构重构（kmmignore 迁移、validator/normalizer 调用链、database_ops 提升均不在此轮范围）
- [ ] 代码改动只触及 spec 文件中列出的具体行
- [ ] 测试必须通过

**SPEC 条款（可测试）**

### 裁定 4 — BUG-2：restore SSE 透传 on_progress
- [ ] SPEC-BUG2-1 `modmgr_web/routes/pipeline.py:107-111` 的 `do_work` 中，`on_progress` 透传给 `restore_from_backup(on_progress=on_progress)`
- [ ] SPEC-BUG2-2 审计全部 9 处 `def do_work(*, on_progress)`，确认 `on_progress` 均被透传且无遗漏

### 裁定 3 — orphan 链路清理
- [ ] SPEC-ORPH-1 `backup_ops.py:661-663` 删除 `_list_orphans()` 调用及 `W_EXTERNAL_FILE_ORPHAN` 警告生成
- [ ] SPEC-ORPH-2 `backup_ops.py:671` `"orphans": orphans` → `"orphans": []`
- [ ] SPEC-ORPH-3 `backup_ops.py` 删除 `delete_orphan_files()` 整函数
- [ ] SPEC-ORPH-4 `backup_ops.py` `__all__` 删除 `"delete_orphan_files"`
- [ ] SPEC-ORPH-5 `restore_ops.py:46` 删除 `orphans: list[str] = []` 字段
- [ ] SPEC-ORPH-6 `restore_ops.py:152` 删除 `"orphans": orphans` 返回键
- [ ] SPEC-ORPH-7 `cli.py` 删除 `delete_orphan_files` import、`--delete-orphans` 参数、orphan 删除调用逻辑
- [ ] SPEC-ORPH-8 测试文件适配：`tests/test_backup_ops.py` 删除 `test_restore_reports_orphans` 和 `test_delete_orphan_files`；`tests/test_restore_ops.py` 移除 `orphans` 键断言；`tests/test_web_api.py` `orphans` 字段不动（已为 `[]`）
- [ ] SPEC-ORPH-9 `backup_ops.py:186-206` `_collect_backup_original_paths()` **保留不动**（被 `detect_dirty_state` 使用）

### 裁定 6 — CODE-3~7 清扫
- [ ] SPEC-CODE-3 `acf_parser.py` 删除 `find_appmanifest_acf_files`、`find_appworkshop_acf_files`（零调用方），`__all__` 同步清理
- [ ] SPEC-CODE-4 `isinstance(rs, list)` 分支在 `userconfig_ops.py:79-82` 为合法旧格式迁移路径，**保留**。`routes/config.py` 已无此代码，CODE-4 自动消除，本轮无需动作
- [ ] SPEC-CODE-5 `preflight.py:27` 和 `preflight.py:61` 删除 `context: CleanContext` 参数；同步修改调用方 `planner_fileops.py:141,143`
- [ ] SPEC-CODE-6 `bootstrap.py:146-147` 注释中的 `source_path` / `first_use` → `config_index`
- [ ] SPEC-CODE-7 `src/modmgr/__init__.py:1` `"""modmanager package."""` → `"""modmgr package."""`
- [ ] SPEC-CODE-7a `src/modmgr_web/__init__.py:1` `"""modmanager_web` → `"""modmgr_web`
- [ ] SPEC-CODE-7b `src/modmgr_web/__init__.py:4` 注释中 `modmanager.orchestrator` → `modmgr.orchestrator`
- [ ] SPEC-CODE-7c `src/modmgr_web/app.py:56` `"package": "modmanager_web"` → `"package": "modmgr_web"`
- [ ] SPEC-CODE-7d `src/modmgr/bootstrap.py:54` 注释中 `modmanager/` → `modmgr/`

### 裁定 2 — 文档修正
- [ ] SPEC-DOC-1 `repo_memo/DESIGN_BOOTSTRAP.md:76` `userconfig_ops._detect_platform_defaults()` → `osplatform.defaultvalue`
- [ ] SPEC-DOC-2 `repo_memo/DESIGN_USERCONFIG_OPS.md:59` `_detect_platform_defaults()` → `osplatform.defaultvalue`

**实现约束**（repo_spec）
- [ ] 改代码前先读相关 `repo_memo/` 文档确认上下文
- [ ] 测试断言只删除 orphan 相关条目，不新增
- [ ] `backup_ops.py:550,567,619` 的 `"orphans": []` 保留（早期返回路径结构稳定）
- [ ] `modmgr_web/adapters.py:94` `"orphans": result.get("orphans", [])` 保留（向后兼容）

**验收标准**
- smith: 上述所有 SPEC 条目对应的代码/文档改动到位
- probe:
  - SPEC-BUG2-1~2：验证 `pipeline.py` restore 端点 on_progress 透传；审计全部 `do_work` 无遗漏
  - SPEC-ORPH-1~9：运行 `tests/test_backup_ops.py`、`tests/test_restore_ops.py`、`tests/test_web_api.py`，orphan 相关测试已删除/适配
  - SPEC-CODE-3~7：`acf_parser.py` 零调用方函数已删；`preflight.py` context 参数已删且调用方同步；注释已修正；包名残留已清理
  - SPEC-DOC-1~2：两个文档的函数名引用已修正
- audit: 确认改动的全局一致性（无遗漏的 orphan 引用、无残留旧函数调用、无注释残留）

**文档落位与收尾**
- 长期结论落位: 已记录在 `work_memo/2026-06-01_TASK_arch_drift_review.md` 裁定 2/3/4/6
- work_memo 收尾: 本轮完成后，arch 指示 smith 将 `work_memo/2026-05-25_pending.md` 中对应条目标记完成

**前置假设与疑虑**
- 假设：用户已确认 CODE-4 自动消除（`userconfig_ops.py:79-82` 为合法迁移路径，`routes/config.py` 无残留）
- 假设：用户已确认 CODE-7 以 `modmgr` 为准，`modmanager_web` → `modmgr_web`
- 疑虑：`tests/test_apply_ops.py:115` 有变量 `tgt = root / "orphan.txt"`——语义与 orphan 链路无关（仅测试文件名），**不动**

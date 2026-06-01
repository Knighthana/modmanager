# inherent_fixes — 固有问题修复测试

> Status: active
> Authority: normative
> Read-Tier: task-scoped
> Purpose: 对 2026-06-01 固有问题修复（commit `d2ae234`）提供黑箱测试断言入口

## 一、适用范围

本文档覆盖以下修复场景的测试断言：

| 裁定 | 场景 | 黑箱标准 |
|------|------|---------|
| 裁定 4 | restore SSE `on_progress` 透传 | 调用方传入回调 → 被调方收到回调并执行 |
| 裁定 3 | orphan 链路删除 | 不存在 `_list_orphans`、`delete_orphan_files`、`W_EXTERNAL_FILE_ORPHAN` |
| 裁定 3 | restore 返回值结构 | restore 返回字典不含 `orphans` 键（或始终为空列表） |
| 裁定 6 | CODE-3 死代码删除 | `acf_parser` 模块无 `find_appmanifest_acf_files` / `find_appworkshop_acf_files` |
| 裁定 6 | CODE-5 preflight 参数 | `run_apply_preflight` / `run_restore_preflight` 不接收 `context` 参数 |
| 裁定 6 | CODE-7 包名 | import `modmgr` 成功，不暴露 `modmanager` 旧名 |

本文档不负责：
- 架构重构后的行为变化（kmmignore 位置、validator 调用点等——见后续 TASK）
- 前端 UI 测试
- 性能测试

---

## 二、裁定 4 — on_progress 透传

### 2.1 黑箱标准

**给定**：一个接受 `on_progress` 回调参数的函数（如 `restore_from_backup`）  
**当**：调用方传入 `on_progress` 回调  
**则**：函数内部在执行过程中至少调用一次该回调

### 2.2 测试断言

- [ ] T-INH-01：`restore_from_backup(backup_dir, on_progress=mock_cb)` → `mock_cb` 被调用至少一次
- [ ] T-INH-02：Web 路由 `pipeline_restore` 的 `do_work` 将 `on_progress` 传入 `restore_from_backup(on_progress=on_progress)`（参数透传验证）
- [ ] T-INH-03：所有 9 处 `def do_work(*, on_progress)` 均将 `on_progress` 透传给下游（审计验证）

---

## 三、裁定 3 — orphan 链路删除

### 3.1 黑箱标准

**给定**：修复后的代码库  
**当**：导入 `backup_ops` 模块  
**则**：不存在 `_list_orphans` 函数、不存在 `delete_orphan_files` 函数、不存在 `W_EXTERNAL_FILE_ORPHAN` 字符串

**给定**：修复后的 `restore_ops` 模块  
**当**：调用 `restore_from_backup`  
**则**：返回值中不包含 `orphans` 键（或以空列表占位）

### 3.2 测试断言

- [ ] T-INH-04：`from modmgr.backup_ops import _list_orphans` → `ImportError`
- [ ] T-INH-05：`from modmgr.backup_ops import delete_orphan_files` → `ImportError`
- [ ] T-INH-06：`backup_ops.__all__` 不含 `"delete_orphan_files"`
- [ ] T-INH-07：`backup_ops.__all__` 不含 `"_list_orphans"`（该函数从未被导出，仅作防御性检查）
- [ ] T-INH-08：`restore_from_backup()` 返回值中 `orphans` 键不存在或为 `[]`
- [ ] T-INH-09：`W_EXTERNAL_FILE_ORPHAN` 不出现在 `backup_ops.py`、`restore_ops.py`、`TERMS_ERROR_CODES.md` 中（全局搜索）

---

## 四、裁定 6 — CODE 清扫

### 4.1 CODE-3：死代码删除

- [ ] T-INH-10：`acf_parser.__all__` 不含 `"find_appmanifest_acf_files"`
- [ ] T-INH-11：`acf_parser.__all__` 不含 `"find_appworkshop_acf_files"`
- [ ] T-INH-12：`from modmgr.acf_parser import find_appmanifest_acf_files` → `ImportError`
- [ ] T-INH-13：`from modmgr.acf_parser import find_appworkshop_acf_files` → `ImportError`

### 4.2 CODE-5：preflight 参数清理

- [ ] T-INH-14：`run_apply_preflight(backup_dirs)` 调用成功（不传 `context` 不报错）
- [ ] T-INH-15：`run_restore_preflight(backup_dirs)` 调用成功（不传 `context` 不报错）
- [ ] T-INH-16：`inspect.signature(run_apply_preflight).parameters` 不含 `"context"`

### 4.3 CODE-7：包名清理

- [ ] T-INH-17：`import modmgr` 成功
- [ ] T-INH-18：`modmgr.__doc__` 不含 `"modmanager"`（或仅出现在历史引用中）
- [ ] T-INH-19：`import modmgr_web` 成功，且 `__doc__` 不含 `"modmanager_web"`

---

## 五、跨裁定 — 回归测试

以下现有测试必须不受影响：

- [ ] T-INH-20：`tests/test_backup_ops.py` 全部通过（orphan 相关测试已删除后）
- [ ] T-INH-21：`tests/test_restore_ops.py` 全部通过（`orphans` 键断言已移除后）
- [ ] T-INH-22：`tests/test_web_api.py` 全部通过（`orphans: []` 占位正常）

---

## 六、实施说明

- 测试代码放置：`tests/test_inherent_fixes.py`
- 测试必须独立于实现细节——只通过公开 API 验证行为
- 允许使用 `pytest.raises(ImportError)` 验证已删除的符号
- 允许使用 `inspect.signature` 验证函数签名
- 不依赖 mock 内部实现，仅 mock 回调行为（T-INH-01）

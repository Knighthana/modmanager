# DESIGN_ORCHESTRATOR — orchestrator 设计规范补充

> 补充于：2026-05-23
> 关联：TASK2605 干跑失效 Bug 修复

---

## §X. PipelineResult 内部契约

### X.1 `dry_run` 必须贯穿全部操作结果

**不变式**：`PipelineResult` 中所有非空的 `*_result` 字段（`backup_result`、`apply_result`、`restore_result`）**必须**包含 `"dry_run": bool` 键。

**适配器契约**：`adapt_pipeline_result()` 必须从每个非空的 `*_result` 中提取 `dry_run` 字段并放入 `data` 字典。

**违反检测**：`PipelineResult.__post_init__` 运行时报错。

### X.2 `_execute_*_plan` 函数签名一致性

三个 `_execute_*_plan` 函数必须使用相同的参数传递模式——**全部接收独立参数**（`entries_by_backup_dir, backup_dirs, dry_run, ...`），禁止在函数体内引用 `plan` 对象。

新增 `_execute_*_plan` 或修改签名时，必须同步检查其余两个。

### X.3 为何用 dataclass `__post_init__` 而非 TypedDict

TypedDict 仅在静态检查时生效（mypy/pyright），不阻止运行时构造不合规的 dict。`__post_init__` 在每次 `PipelineResult(...)` 构造时执行，当场拦截。

此约束不替代测试——测试仍需覆盖干跑开/关两种场景。约束是防御层，测试是验证层。

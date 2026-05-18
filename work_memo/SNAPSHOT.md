# SNAPSHOT — 2026-05-18 文件操作页面工作区适配

## 已完成

### 后端

| 改动 | 文件 |
|------|------|
| `write_backup_dirs` / `read_backup_dirs` 存取完整 backup_dir→files 映射 | `workspacemanager.py` |
| `backup_ws` / `apply_ws` 新增工作区感知函数 | `orchestrator.py` |
| `backup_ws` 存储多目录映射；`apply_ws` 逐目录独立 gate check (FIFO) | `orchestrator.py` |
| `backup()` 签名改为 `backup_dirs: dict[str, list[str]]`，遍历多目录 | `orchestrator.py` |
| `apply()` 加 `on_progress` 透传 | `orchestrator.py` |
| 三个 workspace 端点：`POST /{id}/pipeline/backup` / `apply` / `restore` | `routes/workspace.py` |
| `WorkspaceBackupRequest` / `WorkspaceApplyRequest` / `WorkspaceRestoreRequest` | `schemas.py` |
| `adapt_pipeline_result` 暴露 `backed_up` / `applied` / `backup_errors` / `dry_run` | `adapters.py` |
| `adapt_restore_result` 透传 `dry_run` | `adapters.py` |
| `get_game_backup_id` 重写：StateFlags∈{4} + buildid → hex | `backup_ops.py` |
| `get_workshop_timestamphex` 新增：per-contentid T_local vs T_remote | `backup_ops.py` |
| `get_workshop_latest_timeupdated` 新增：读 WorkshopItemDetails.{contentid}.latest_timeupdated | `acf_parser.py` |
| `get_workshop_timeupdated` 扩展：contentid 针对性查找 | `acf_parser.py` |
| `build_backup_dirs` 新增：per-contentid/app 多目录输出，path prefix 匹配 | `backup_dir_builder.py` |
| `build_backup_dir` 改为兼容 wrapper | `backup_dir_builder.py` |
| `run_differential_backup` dry_run：`action:"copy"` + `backup_path` + 目录路径尾 `/` | `backup_ops.py` |
| `apply_final_mapping` dry_run：目录路径尾 `/` | `backup_ops.py` |
| 进度回报：`run_differential_backup` / `apply_final_mapping` / `restore_from_backup` 全部支持逐文件 `on_progress` | `backup_ops.py` |
| `restore` 端点遍历全部 backup_dirs | `routes/workspace.py` |
| 引擎函数重写：`backup()`/`apply()`/`restore()`/`run()` KISS 签名，内部调 `build_backup_dirs` | `orchestrator.py` |
| `_ws` 函数简化：退化为翻译工作区语境 + 委托引擎 | `orchestrator.py` |
| `restore_ws()` 新增 | `orchestrator.py` |
| `WorkspaceRestoreRequest`: `dry_run` → `force` | `schemas.py` |
| bakprefix → baksuffix 全量迁移（命名格式 + user_config + 文档） | 17 个文件 |
| 硬编码防护 `startswith("kmmbackup_")` → `endswith(".kmmbackup")` | `backup_ops.py` |
| `gitignore-parser` 依赖加入 `pyproject.toml` | `pyproject.toml` |

### 前端

| 改动 | 文件 |
|------|------|
| 移除 `DatabaseSelector`，改为 workspaceId 路由绑定 | `OperationsPage.vue` |
| 映射摘要：移除"树总数"，新增"操作警告/操作错误" | `OperationsPage.vue` |
| mappingStats 从 `final_mapping[].request.action` 统计 | `OperationsPage.vue` |
| 警告/错误：0 不弹气泡，>0 点击弹出详情 dialog | `OperationsPage.vue` |
| 加载态/错误态/空态三分支 | `OperationsPage.vue` |
| dry_run 覆盖三种操作 | `OperationsPage.vue` |
| dry_run 文件列表持久表格：操作、类型、备份位置、源路径、大小、修改时间 | `OperationsPage.vue` |
| 操作列：`copy`→"拷贝"标签，`create/replace/delete`→对应标签 | `OperationsPage.vue` |
| 摘要列宽统一：`table-layout: fixed` + 标签固定 80px | `OperationsPage.vue` |
| locale 更新：`mappingWarnings`/`mappingErrors`/`operationWarnings`/`operationErrors` | `zh-CN.ts` |
| 移除旧 `API_ENDPOINTS` 常量、`generateBackupDir`、旧 OperationsPage 测试 | 多个文件 |

### 文档

| 文档 | 状态 |
|------|------|
| `DESIGN_BACKUP.md` | 重写完成：时间戳来源、稳定性检查、per-contentid 目录规则、多库同名表格、dry_run 输出格式、核心函数签名 |
| `DESIGN_GUI.md` §3.6 | 更新为工作区模式 |
| `DESIGN_REST_API.md` | restore 移除"后续实现"；BackupRequest/ApplyRequest 废弃；schema 更新 |
| `DESIGN_ORCHESTRATOR.md` | backup() 加 dry_run 参数；元数据日期 |
| `DESIGN_COMM_PROTOCOL.md` | 端点表迁移到 workspace 前缀 |
| `DESIGN_COMPUTE_PREP_PAGE.md` | 旧路径更新 |
| `DESIGN_DATA_CLEANUP.md` | 旧路径更新 |
| `DESIGN_EXECUTION_PLAN.md` | 旧路径更新 |
| `DESIGN_FRONTEND_LAYER_INDEPENDENCE.md` | 旧路径更新 |
| `PLAN_operations_workspace_adapt.md` | 施工文件：完整改造方案 + 三轮修正 + backup_id 规则 |
| `PLAN_dry_run_output_spec.md` | dry_run 输出字段规范 + 前端表格列定义 |

---

## 待实现 / 未完成

### 硬编码后缀与可配置 baksuffix 不一致
`backup_ops.py` 硬编码 `_HARDCODED_BACKUP_SKIP_SUFFIX = ".kmmbackup"`。用户可通过 `user_config.baksuffix` 修改后缀，硬编码不会跟随变化。但同时设计约定是引擎内部**写死**忽略 `.kmmbackup`——这是有意为之的安全底线。当前行为符合设计。

### bakignore 规则未接入引擎
- `load_bakignore_rules` 仍是死代码——定义了但从未被 `backup()`/`apply()`/`restore()` 调用
- `gitignore-parser` 已安装为依赖，但未在引擎流程中接线
- `.kmmbakignore` 拷贝逻辑（backup 拷入、apply 拷出）未实现

### 前端 dry_run 表格对 apply 的支持
apply 的字段名是 `target`/`source`，列渲染依赖 `row.backup_path || row.target || row.path` 的 fallback。逻辑正确但未经端到端验证。

### 文档待更新
- `DESIGN_ORCHESTRATOR.md`：引擎函数签名已全面重写，文档未同步
- `DESIGN_BACKUP.md` §6：未补 `restore()` / `restore_ws()` 签名
- `DESIGN_REST_API.md`：restore 端点已更新但文档可能未同步

---

## 架构决策记录

1. **每个 contentid 独立备份**：各自在自己的根目录下创建 backup dir，backup_id 各算各的
2. **path prefix 匹配决定归属**：不依赖 appid 计数，"选择匹配数最多的 appid"逻辑已废弃
3. **baksuffix 从 user_config 严格读取**：不硬编码，照抄原值
4. **app backup_id**：StateFlags ∈ {4} → buildid → hex
5. **contentid backup_id**：T_local ≥ T_remote → T_remote → hex；T_local < T_remote → 不稳定跳过
6. **apply gate check per-dir FIFO**：不阻塞，一个失败不阻止其他
7. **apply 不比对 hash**：只查"有无"
8. **同步模型**：不引入 async，避免染色传染
9. **引擎函数自给自足**：接受 `(final_mapping, database, user_config, flags)`，内部调 `build_backup_dirs`，不依赖外部传入 backup_dirs
10. **_ws 只做翻译**：工作区语境 → 消费品 → 委托引擎，不代引擎做决策
11. **restore 独立原语**：与 backup 解耦，自己从 final_mapping 推导 backup_dir，不依赖 backup_ws 存储的映射
12. **备份目录命名**：点分后缀格式 `{id}.{hex}.{baksuffix}/`，baksuffix 从 user_config 读取
13. **硬编码防护底线**：引擎内部写死忽略 `.kmmbackup` 后缀目录，不受 user_config 影响

---

## 提交记录

```
7650b7d feat: per-contentid backup dirs, stability checks, workspace-aware OperationsPage
3102c17 docs: update backup design
7d31579 feat: dry_run output spec — add action+backup_path fields
7e6416b fix: directory paths in dry_run output must end with trailing /
a6e7e7b fix: per-backup_dir gate check in apply_ws, store full mapping
7940c8c docs: session snapshot
ae9461b refactor: bakprefix → baksuffix — suffix naming, hardcoded skip, gitignore-parser
3bc0869 feat: engine/_ws separation — KISS engine functions, simplified _ws delegates
```

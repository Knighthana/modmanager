# REST API 设计

> Status: partially-stable
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 约束 Web API 的接口形态、SSE 通信方式与 Web 层行为边界
>
> Last update: 2026-05-20
>
> 重要更新（2026-06-03）：generic pipeline 端点**全部清退**。
> - `POST /api/pipeline/backup`、`POST /api/pipeline/apply` — 已删除
> - `POST /api/pipeline/compute`、`POST /api/pipeline/run`、`POST /api/pipeline/visualize`、`POST /api/pipeline/restore` — 已删除（`routes/pipeline.py` 整文件删除）
> - 所有流水线端点迁移为 workspace 感知：`POST /api/workspace/{workspace_id}/pipeline/*`

## 1. 概览（要点）
- 事实源（实现文件）：[src/modmgr_web/schemas.py](src/modmgr_web/schemas.py)、[src/modmgr_web/adapters.py](src/modmgr_web/adapters.py)、[src/modmgr_web/app.py](src/modmgr_web/app.py)、[src/modmgr_web/routes/workspace.py](src/modmgr_web/routes/workspace.py)、[src/modmgr_web/sse.py](src/modmgr_web/sse.py)、[src/modmgr/orchestrator/__init__.py](src/modmgr/orchestrator/__init__.py)。
- 原则：所有流水线执行入口必须走工作区路由（`/api/workspace/{id}/pipeline/*`）。generic `/api/pipeline/*` 端点已整体清退。前端请求一律带 `workspaceId`，`backup_dir` 文件路径不出现在 API 响应中。
- CLI 路径：CLI 侧通过 `dispatch()` 直接构造 `TaskRequest`（`resolver_type=raw_dict` 或 `file_paths`），不经过 Web 路由，不依赖 generic pipeline 端点。

## 2. 通用响应格式（ApiResponse）
所有非 SSE 的 JSON 响应采用统一包封：
```json
{
  "ok": true|false,
  "data": {...} | null,
  "errors": [...],
  "warnings": [...]
}
```
规则：`errors` 与 `warnings` 字段恒存在；当无内容时返回空数组 `[]`（无则空）。

SSE 端点最终会发送一个 `event: result`，其 `data` 部分采用上述 ApiResponse 的字典结构（由适配器 `adapt_pipeline_result` / `adapt_dict_result` / `adapt_restore_result` 序列化）。

## 3. 端点清单（摘要）

全局 / 非工作区（generic）:
- `GET /api/health` — 健康检查（JSON）
- `POST /api/config/discover` — 发现并返回 `user_config`（JSON）
- `POST /api/config/save` — 保存 `user_config`（JSON）
- `POST /api/database/generate` — 生成 database（SSE）
- `POST /api/database/read` — 读取 database（JSON）
- `POST /api/database/save` — 保存 database（JSON）
- `POST /api/rules/scan` — 扫描目录列出规则文件（JSON）
- `POST /api/rules/read` — 读取单个规则文件（JSON）
- `POST /api/rules/affected-entries` — 规则影响查询（JSON）
- `POST /api/backups/list` — 列出备份摘要（JSON）
- `POST /api/backups/inspect` — 检查备份详情（JSON）

> 注：generic `/api/pipeline/*` 端点（compute / run / visualize / restore）已整体清退，迁移到 workspace 感知端点。前端请求一律通过 `/{workspace_id}/pipeline/*` 路由。

工作区感知（product 主路径）:
- `POST /api/workspace/create` — 创建工作区（JSON）
- `POST /api/workspace/{id}/delete` — 删除工作区（JSON）
- `GET /api/workspace/list` — 列出工作区（JSON）
- `GET /api/workspace/{id}/meta` — 工作区元信息（JSON）
- `POST /api/workspace/{id}/rules/aggregate` — 聚合规则并写入工作区（JSON）
- `GET  /api/workspace/{id}/rules/aggregated` — 读取已聚合规则（JSON）
- `POST /api/workspace/{id}/pipeline/compute` — 在工作区上下文计算（SSE）。**请求体：无**，聚合规则与决策从工作区目录读取；结果写回工作区（mapping、svg、fingerprints）。
- `POST /api/workspace/{id}/pipeline/backup` — 在工作区上下文做差异备份（SSE）。请求体：`{ "dry_run": bool }`。
- `POST /api/workspace/{id}/pipeline/apply` — 在工作区上下文提交 apply（SSE）。请求体：`{ "dry_run": bool }`。此路由会调用 `dispatch()` 传入 `Intent.APPLY`，通过 Resolver → Planner → 原语管线执行；最终由 `apply_entries()` 执行文件替换。
- `POST /api/workspace/{id}/pipeline/restore` — 在工作区上下文恢复（SSE）。请求体：`{ "force": bool }`。
- `POST /api/workspace/{id}/pipeline/run` — 在工作区上下文执行全流水线（SSE）。**请求体：无**（当前实现从工作区读取所有输入）。
- `POST /api/workspace/{id}/pipeline/visualize` — 在工作区上下文生成森林可视化（JSON/SSE）。从工作区读取 `aggregated_rule` 和 `mapping`。
- `POST /api/workspace/{id}/decisions/save`、`GET /api/workspace/{id}/decisions/load` — 保存/读取决策（JSON）
- `GET /api/workspace/{id}/forest/svg` — 读取 SVG（image/svg+xml）
- `GET /api/workspace/{id}/forest/mapping` — 读取 mapping（JSON）

注意：适配器返回的 `data` 字段不包含任何文件系统路径。资源寻址通过 `workspaceId` 完成。

> 说明：上面列出的请求体形态与实现同步，以 [src/modmgr_web/schemas.py](src/modmgr_web/schemas.py) 为权威定义。特别注意：工作区的 `compute` / `run` 路由不需要也不会接受 `aggregated_rule_set` 等计算输入——它们从工作区目录读取。

## 4. SSE 使用示例（典型）

- Workspace run（工作区主路径）：
```http
POST /api/workspace/{workspace_id}/pipeline/run
Content-Type: application/json
```
返回：`text/event-stream`，先若干 `event: progress`，最后 `event: result`，其中 `data` 是 ApiResponse（由 `adapt_pipeline_result` 序列化）。全部输入从工作区读取，请求体无聚合规则等计算参数。

- Workspace apply（工作区主路径）：
```http
POST /api/workspace/{workspace_id}/pipeline/apply
Content-Type: application/json

{ "dry_run": false }
```
行为：后端通过 `dispatch(Intent.APPLY)` 进入 Resolver → Planner → 原语管线执行；全部上下文（mapping、backup_dir、database）由工作区解析，不从请求体读取。

## 5. Pydantic schema（参考实现）
详见 [src/modmgr_web/schemas.py](src/modmgr_web/schemas.py)。要点：
- Workspace 端点使用 `WorkspaceBackupRequest` / `WorkspaceApplyRequest` / `WorkspaceRestoreRequest`（仅含控制字段如 `dry_run` / `force`）
- `Generic RunRequest` / `ComputeRequest` 已随 generic pipeline 端点清退（CLI 侧直接构造 `TaskRequest`，不经过 Pydantic schema）
- `ApiResponse` 为统一输出信封（见第 2 节）

## 6. 适配器（adapters）
实现中的 `adapt_pipeline_result(pr: PipelineResult)` 会把 `PipelineResult` 映射为 ApiResponse 字典，包含字段：
- `data.trees`, `data.final_mapping`, `data.mapping_result`
- 若有 `backup_result`：`data.backed_up`, `data.backup_skipped`, `data.backup_errors`, `data.dry_run`
- 若 `apply_result`：`data.applied`, `data.apply_skipped`, `data.apply_errors`, `data.apply_warnings`, `data.apply_diagnostics`, `data.dry_run`

> 注：`data.backup_dir` 字段已废弃——API 响应不再暴露文件系统路径，前端通过 `workspaceId` 索引资源。

实现文件：[src/modmgr_web/adapters.py](src/modmgr_web/adapters.py)

## 7. FastAPI 工厂（app.py）行为要点
实现文件：[src/modmgr_web/app.py](src/modmgr_web/app.py)
- CORS 仅在开发态启用；生产态（存在 `frontend/dist/index.html`）不挂载 CORS 中间件。
- 开发态可通过环境变量 `KMM_CORS_ORIGINS` 覆盖允许源（逗号分隔）。
- 路由注册使用 prefix：
  - `/api/config`, `/api/database`, `/api/pipeline`, `/api/rules`, `/api/backups`, `/api/workspace`

## 8. 已删除的端点（本轮清退）
- `POST /api/pipeline/backup`（generic 执行入口） — 已删除，备份执行请使用工作区端点。
- `POST /api/pipeline/apply`（generic 执行入口） — 已删除，apply 执行请使用工作区端点。

> 注：如果历史原因需要保留只读或审计视图，请使用 `/api/backups/*` 只读端点，不要重新开放 generic 执行入口。

## 9. 验收与检验建议
- 快速尾查：建议在仓库中搜索这些关键字以确认已移除或更新旧端点与旧模型：`api/pipeline/backup`、`api/pipeline/apply`、`BackupRequest`、`ApplyRequest`、`adapt_backup_result`、`adapt_apply_result`。
- 文档与实现一致性核对：对照 [src/modmgr_web/schemas.py](src/modmgr_web/schemas.py) 的 request model；对照 [src/modmgr_web/adapters.py](src/modmgr_web/adapters.py) 的 `adapt_pipeline_result` 字段映射，确认 `data.backup_dir` 的行为与本文件声明一致。
- 前端/测试覆盖核对：检查 frontend、repo_test 及 `tests` 目录中是否存在误导性旧文案或对旧 generic 端点的调用，并更新说明。

## 10. 变更历史记录（简短）
- 2026-05-16: 工作区模型引入，流水线端点迁移到 `/api/workspace/{id}/...`
- 2026-05-20: 文档收口：移除 generic 执行入口 `/api/pipeline/backup` 与 `/api/pipeline/apply`，并把 schema/adapter/示例改为与实现一致。

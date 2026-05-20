# REST API 设计

> Status: partially-stable
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 约束 Web API 的接口形态、SSE 通信方式与 Web 层行为边界
>
> Last update: 2026-05-20
>
> 重要更新（2026-05-20）：本文件已对齐当前实现。
> - 已删除的 generic 执行入口：`POST /api/pipeline/backup`、`POST /api/pipeline/apply`（这两条 generic 执行端点已从实现中移除，备份/应用主路径仅允许通过工作区 API）
> - 保留的 generic pipeline 端点（仍对外提供）：`POST /api/pipeline/compute`、`POST /api/pipeline/run`、`POST /api/pipeline/visualize`、`POST /api/pipeline/restore`
> - 工作区感知流水线：所有文件系统写入相关的主路径为 `POST /api/workspace/{workspace_id}/pipeline/*`（compute / backup / apply / restore / run）

## 1. 概览（要点）
- 事实源（实现文件）：[src/modmanager_web/schemas.py](src/modmanager_web/schemas.py)、[src/modmanager_web/adapters.py](src/modmanager_web/adapters.py)、[src/modmanager_web/app.py](src/modmanager_web/app.py)、[src/modmanager_web/routes/pipeline.py](src/modmanager_web/routes/pipeline.py)、[src/modmanager_web/routes/workspace.py](src/modmanager_web/routes/workspace.py)、[src/modmanager_web/sse.py](src/modmanager_web/sse.py)、[src/modmanager/orchestrator/__init__.py](src/modmanager/orchestrator/__init__.py)。
- 原则：任何会写磁盘或执行备份/应用的执行入口必须走工作区路由（`/api/workspace/{id}/pipeline/*`）。generic `/api/pipeline/*` 提供的是无工作区（非写盘）或供脚本化使用的端点，但不再负责 workspace-scoped backup/apply 执行。

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
- `POST /api/pipeline/compute` — 计算映射（SSE） — 需在 body 提供 `aggregated_rule_set`
- `POST /api/pipeline/run` — 全流水线（SSE） — 需在 body 提供 `aggregated_rule_set`（generic run）
- `POST /api/pipeline/visualize` — 可视化（JSON）
- `POST /api/pipeline/restore` — 恢复（SSE）

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
- `POST /api/workspace/{id}/decisions/save`、`GET /api/workspace/{id}/decisions/load` — 保存/读取决策（JSON）
- `GET /api/workspace/{id}/forest/svg` — 读取 SVG（image/svg+xml）
- `GET /api/workspace/{id}/forest/mapping` — 读取 mapping（JSON）

注意：适配器在返回中可能包含 `data.backup_dir`（见第 6 节）；该字段仅为结果暴露，用于前端展示或审计，并不表示重新开放 generic 写盘执行入口或作为触发写盘行为的接口。

> 说明：上面列出的请求体形态与实现同步，以 [src/modmanager_web/schemas.py](src/modmanager_web/schemas.py) 为权威定义。特别注意：工作区的 `compute` / `run` 路由不需要也不会接受 `aggregated_rule_set` 等计算输入——它们从工作区目录读取。

## 4. SSE 使用示例（典型）
- Generic run（需要在 body 中传入 `aggregated_rule_set`）：
```http
POST /api/pipeline/run
Content-Type: application/json

{
  "database_name": "default",
  "aggregated_rule_set": { /* 必填 */ },
  "dry_run": false
}
```
返回：`text/event-stream`，先若干 `event: progress`，最后 `event: result`，其中 `data` 是 ApiResponse（由 `adapt_pipeline_result` 序列化）。

- Workspace apply（工作区主路径）：
```http
POST /api/workspace/{workspace_id}/pipeline/apply
Content-Type: application/json

{ "dry_run": false }
```
行为：后端通过 `dispatch(Intent.APPLY)` 进入 Resolver → Planner → 原语管线执行；全部上下文（mapping、backup_dir、database）由工作区解析，不从请求体读取。

## 5. Pydantic schema（参考实现）
详见 [src/modmanager_web/schemas.py](src/modmanager_web/schemas.py)。要点：
- Generic `RunRequest` / `ComputeRequest` 需要 `aggregated_rule_set`（generic 端点）
- Workspace 端点使用 `WorkspaceBackupRequest` / `WorkspaceApplyRequest` / `WorkspaceRestoreRequest`（仅含控制字段如 `dry_run` / `force`）
- `ApiResponse` 为统一输出信封（见第 2 节）

## 6. 适配器（adapters）
实现中的 `adapt_pipeline_result(pr: PipelineResult)` 会把 `PipelineResult` 映射为 ApiResponse 字典，包含字段：
- `data.trees`, `data.final_mapping`, `data.mapping_result`
- 若有 `backup_result`：`data.backed_up`, `data.backup_skipped`, `data.backup_errors`, `data.dry_run`
- 若有 `apply_result`：`data.applied`, `data.apply_skipped`, `data.apply_errors`, `data.apply_warnings`, `data.apply_diagnostics`, `data.dry_run`
- 若 `pr.backup_dir` 存在，会带出 `data.backup_dir`

实现文件：[src/modmanager_web/adapters.py](src/modmanager_web/adapters.py)

## 7. FastAPI 工厂（app.py）行为要点
实现文件：[src/modmanager_web/app.py](src/modmanager_web/app.py)
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
- 文档与实现一致性核对：对照 [src/modmanager_web/schemas.py](src/modmanager_web/schemas.py) 的 request model；对照 [src/modmanager_web/adapters.py](src/modmanager_web/adapters.py) 的 `adapt_pipeline_result` 字段映射，确认 `data.backup_dir` 的行为与本文件声明一致。
- 前端/测试覆盖核对：检查 frontend、repo_test 及 `tests` 目录中是否存在误导性旧文案或对旧 generic 端点的调用，并更新说明。

## 10. 变更历史记录（简短）
- 2026-05-16: 工作区模型引入，流水线端点迁移到 `/api/workspace/{id}/...`
- 2026-05-20: 文档收口：移除 generic 执行入口 `/api/pipeline/backup` 与 `/api/pipeline/apply`，并把 schema/adapter/示例改为与实现一致。

# web_purification — Web 层净化

> Status: active
> Authority: normative
> Read-Tier: task-scoped
> Purpose: 裁定 8/9/15 的测试断言 — 验证 Web 路由层清除非 workspace 端点、强制 resolver_type、移除 backup_dir 字段
> 依据: `DESIGN_REST_API.md`、`DESIGN_ORCHESTRATOR_CONTRACT.md`、`DESIGN_WORKSPACE_MODEL.md`、`work_memo/2026-06-01_TASK_arch_drift_review.md` 裁定 8/9/15

---

## 一、裁定 8：Web resolver_type 强制

### 断言

| # | 断言 | 级别 |
|---|------|:---:|
| T-WP-01 | Web 层所有 `TaskRequest` 构造的 `resolver_type` 为 `"workspace"` | MUST |
| T-WP-02 | Web 层不使用 `resolver_type="raw_dict"` | MUST |
| T-WP-03 | Web 层不使用 `resolver_type="file_paths"` | MUST |
| T-WP-04 | `DESIGN_ORCHESTRATOR_CONTRACT.md` 中包含 `resolver_type="workspace"` 作为 L1 硬约束 | MUST |

---

## 二、裁定 9：pipeline.py 删除 + 前端迁移

### 2.1 后端

| # | 断言 | 级别 |
|---|------|:---:|
| T-WP-05 | `src/modmgr_web/routes/pipeline.py` 文件不存在 | MUST |
| T-WP-06 | `app.py` 不注册 `/api/pipeline` 路由 | MUST |
| T-WP-07 | `app.py` 不 import `pipeline` 路由模块 | MUST |
| T-WP-08 | `POST /{workspace_id}/pipeline/visualize` 端点存在（workspace.py 中） | MUST |
| T-WP-09 | 原 generic 端点 `/api/pipeline/compute`、`/api/pipeline/run`、`/api/pipeline/restore` 不可访问 | MUST |

### 2.2 前端

| # | 断言 | 级别 |
|---|------|:---:|
| T-WP-10 | `stores/forest.ts` 中 `compute` 请求使用 `/{workspaceId}/pipeline/compute` | MUST |
| T-WP-11 | `stores/forest.ts` 中 `run` 请求使用 `/{workspaceId}/pipeline/run` | MUST |
| T-WP-12 | `components/BackupPage.vue` 中 restore 请求使用 `/{workspaceId}/pipeline/restore`，传入 `workspaceId` 而非 `backup_dir` | MUST |

---

## 三、裁定 15：移除 backup_dir API 字段

### 断言

| # | 断言 | 级别 |
|---|------|:---:|
| T-WP-13 | `PipelineResult` 不含 `backup_dir: str` 字段（或改为 `workspace_id`） | MUST |
| T-WP-14 | `adapters.py` 中 `adapt_pipeline_result()` 不输出 `data.backup_dir` | MUST |
| T-WP-15 | API 响应 JSON 中不出现 `backup_dir` 文件系统路径字段 | MUST |
| T-WP-16 | 前端不依赖 `backup_dir` 字段来导航或展示 | MUST |

### 文档一致性

| # | 断言 | 级别 |
|---|------|:---:|
| T-WP-17 | `DESIGN_REST_API.md` 不含 generic pipeline 端点描述 | MUST |
| T-WP-18 | `DESIGN_COMM_PROTOCOL.md` 中 pipeline 端点为 workspace 感知格式 | MUST |
| T-WP-19 | `DESIGN_WORKSPACE_MODEL.md` 中 pipeline 端点含 `/visualize` | MUST |
| T-WP-20 | `DESIGN_REST_API.md` 中不含 `backup_dir` 响应字段 | MUST |

---

## 四、验收标准

- [ ] 全部 T-WP-01 ~ T-WP-20 通过
- [ ] `POST /{workspace_id}/pipeline/visualize` 新增端点功能正常
- [ ] 前端 3 处端点迁移后功能不变
- [ ] API 响应不再泄露文件系统路径

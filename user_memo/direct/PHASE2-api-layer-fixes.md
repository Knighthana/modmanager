# Phase 2 — API 对齐基线（已落地）

> Status: aligned
> Authority: user-guidance
> Purpose: 保留 API 层改造目标，并与当前契约保持一致

---

## 一、目标

本阶段目标是让 Web API 和前端契约一致，避免历史字段与旧端点继续渗透到实现中。

当前生效原则：
1. database/config/rules/backups 端点按稳定契约使用。
2. pipeline 端点按演进契约使用（与 GUI 决策流联动）。
3. 不再引入 workspace 后端端点。

---

## 二、当前对齐状态（实现基线）

### 2.1 schemas 与 routes
- 已对齐：database 读写使用 `database_name` 语义。
- 已对齐：compute/run 支持 `aggregated_rule_set` 与决策参数。
- 已对齐：rules 相关端点沿用 scan/read/aggregate/affected-entries/load-aggregated。

### 2.2 workspace 责任边界
- 已对齐：workspace 状态在前端 localStorage 管理。
- 已对齐：后端不提供 workspace save/status 端点。

---

## 三、implement 约束（禁止回退）

1. 不恢复 `/api/workspace/*` 路由。
2. 不在请求体中回退到 `database` 任意 dict/path 混传模式。
3. 不恢复 `user_config_path`、`output_path`、`cache_path` 这类旧入口字段。
4. 新增 API 字段前，先在 repo_memo 的 REST API 文档落盘。

---

## 四、增量任务模板（未来再改 API 时复用）

1. 先更新契约文档（repo_memo）。
2. 再改 `schemas.py`。
3. 再改对应 `routes/*`。
4. 最后补测试并跑门禁。

---

## 五、门禁

1. Python 测试通过。
2. 前端测试与构建通过。
3. 与 repo_memo 的 API 文档无冲突。

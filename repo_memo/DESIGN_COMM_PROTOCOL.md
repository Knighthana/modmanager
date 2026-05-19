# DESIGN_COMM_PROTOCOL — 通讯协议设计

> Status: active
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 冻结 Web API 通信协议契约——REST 响应格式、SSE 事件流生命周期与数据结构、错误码约定。作为前后端对接的硬约束。
> 创建：2026-05-09
> 依赖：`repo_spec/sse_event.schema.json`、`repo_spec/branch_decisions.schema.json`、`DESIGN_REST_API.md`

---

## 1. 协议总览

本项目使用两种通信协议：

| 协议 | 用途 | 传输方式 |
|------|------|----------|
| **REST** | 短耗时操作（查询、配置读写、健康检查） | HTTP POST/GET → JSON 响应 |
| **SSE** | 长耗时操作（Steam 扫描、计算、备份、恢复、全流水线） | HTTP POST → `text/event-stream` 流式响应 |

两种协议共享同一响应外壳 `ApiResponse`。SSE 是 REST 的超集：最终 `result` 事件携带的 payload 与 REST 响应格式完全相同。

---

## 2. ApiResponse 通用响应格式

所有 REST 端点和 SSE `result` 事件均返回此结构。

### 2.1 Schema

```json
{
  "ok": true,
  "data": { ... },
  "errors": [],
  "warnings": []
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `ok` | `boolean` | 操作是否成功。`false` 时 `data` 为 `null` |
| `data` | `object \| null` | 操作产出数据；结构因端点而异 |
| `errors` | `string[]` | 致命错误列表。每项以 `E_` 错误码开头 |
| `warnings` | `string[]` | 非致命警告列表。每项以 `W_` 警告码开头 |

### 2.2 错误码约定

- 致命错误以 `E_` 前缀开头（如 `E_KMM_RULE_LOAD_FAILED`）
- 警告以 `W_` 前缀开头（如 `W_FOREST_BRANCHING`）
- 错误码清单参见 `DESIGN_ENGINE_INVARIANTS.md` 和 `DESIGN_RULE_AGGREGATOR.md` §10

---

## 3. REST 协议

### 3.1 端点的 REST 动词

全部操作类端点使用 `POST`。仅 `GET /api/health` 为 `GET`。

### 3.2 请求格式

- `Content-Type: application/json`
- 路径参数置于请求 body 中（非 URL path 参数）
- 路由端点在接收路径输入后，调用 `path_resolver` 进行 `~` / 环境变量展开及规范化

### 3.3 响应格式

- `Content-Type: application/json`
- HTTP 状态码：成功 `200`，参数校验失败 `422`（Pydantic），运行时错误 `500`
- 响应体一律为 `ApiResponse` 格式

### 3.4 端点清单

详见 `DESIGN_REST_API.md` §4.2。

| 方法 | 路径 | 流式 | 说明 |
|------|------|:--:|------|
| `GET` | `/api/health` | — | 健康检查 |
| `POST` | `/api/config/discover` | — | 发现 user_config |
| `POST` | `/api/config/save` | — | 保存 user_config |
| `POST` | `/api/database/generate` | SSE | 扫描 Steam 库生成 database |
| `POST` | `/api/database/read` | — | 读取指定 database 内容 |
| `POST` | `/api/database/save` | — | 保存 database |
| `POST` | `/api/pipeline/visualize` | — | Forest JSON → SVG/ASCII/DOT |
| `POST` | `/api/workspace/{id}/pipeline/compute` | SSE | 工作区上下文内计算映射 |
| `POST` | `/api/workspace/{id}/pipeline/backup` | SSE | 工作区上下文内差异备份 |
| `POST` | `/api/workspace/{id}/pipeline/apply` | SSE | 提交工作区 apply 任务给后端编排 |
| `POST` | `/api/workspace/{id}/pipeline/restore` | SSE | 工作区上下文内恢复备份 |
| `POST` | `/api/workspace/{id}/pipeline/run` | SSE | 工作区上下文内全流水线 |
| `POST` | `/api/rules/scan` | — | 扫描目录列出 kmm_rule 文件 |
| `POST` | `/api/rules/read` | — | 读取单个 kmm_rule 文件内容 |
| `POST` | `/api/workspace/{id}/rules/aggregate` | SSE | 工作区上下文内聚合规则 |
| `POST` | `/api/rules/affected-entries` | — | 查询聚合规则影响的 game/mod |
| `GET` | `/api/workspace/{id}/rules/aggregated` | — | 读取工作区已聚合规则 |
| `POST` | `/api/backups/list` | — | 列出备份目录摘要 |
| `POST` | `/api/backups/inspect` | — | 查看备份详情 |

协议冻结说明：

- `/api/pipeline/backup` 与 `/api/pipeline/apply` 已从实现中删除，不属于当前有效协议契约。
- 禁止恢复 generic backup/apply 执行入口。
- backup/apply 的产品主路径仅允许 workspace 路由。

---

## 4. SSE 协议

### 4.1 流生命周期

```
Client                              Server
  │                                    │
  ├── POST /api/workspace/{id}/pipeline/run ─→│  (JSON body)
  │                                    │
  │←── event: progress ────────────────┤  (N 次，直至完成)
  │    data: {"type":"progress", ...}   │
  │                                    │
  │←── event: result ──────────────────┤  (1 次，最终)
  │    data: {"type":"result", ...}     │
  │                                    │
  │  (HTTP 连接关闭)                    │
```

或异常路径：

```
Client                              Server
  │                                    │
  ├── POST /api/workspace/{id}/pipeline/run ─→│
  │                                    │
  │←── event: progress ────────────────┤
  │←── event: error ───────────────────┤  (1 次，终止)
  │    data: {"type":"error", ...}      │
  │                                    │
  │  (HTTP 连接关闭)                    │
```

**关键约束**：
- `result` 和 `error` 是**终端事件**——出现后流结束，连接关闭
- `progress` 事件可出现 0 到 N 次
- 一个流中 `result` 和 `error` 互斥，不会同时出现

### 4.2 SSE 事件类型

三种事件类型的 JSON Schema 定义见 `repo_spec/sse_event.schema.json`。

#### 4.2.1 `progress` — 进度更新

```
event: progress
data: {"type":"progress","step":"aggregate","finished":0,"total":1,"message":"Aggregating rules..."}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `"progress"` | 事件类型 |
| `step` | `string` | 当前流水线阶段标识：`"aggregate"` / `"compute"` / `"backup"` / `"apply"` / `"scan"` 等 |
| `finished` | `integer` (≥0) | 当前阶段已完成工作单元数 |
| `total` | `integer` (≥-1) | 当前阶段总工作单元数。`-1` 表示总数未知 |
| `message` | `string` | 人可读的进度描述 |

**约定**：
- 同一阶段内 `finished` 从 0 递增至 `total`
- 阶段切换时 `step` 改变，`finished` 重置
- `total = -1` 时前端宜显示不确定进度（indeterminate）

#### 4.2.2 `result` — 操作完成

```
event: result
data: {"type":"result","payload":{"ok":true,"data":{...},"errors":[],"warnings":[]}}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `"result"` | 事件类型 |
| `payload` | `object` | `ApiResponse` 结构（见 §2.1） |

#### 4.2.3 `error` — 未处理异常

```
event: error
data: {"type":"error","message":"Something went wrong"}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | `"error"` | 事件类型 |
| `message` | `string` | 异常描述（调试用；生产环境中对本地用户有诊断价值，故保留原始信息） |

**注意**：`error` 事件与 `ApiResponse.errors` 不同。
- `ApiResponse.errors`：业务层已知错误（如权限不足、文件不存在），包含错误码
- SSE `error` 事件：桥接层未捕获的异常（如线程崩溃），通常意味着严重故障

---

## 5. 桥接层（后台线程 → asyncio）

### 5.1 架构

SSE 端点的同步业务逻辑在不阻塞事件循环的前提下，通过 `asyncio.Queue` + `ThreadPoolExecutor` 桥接到异步流。

```
  FastAPI async route
       │
       ├─ loop.run_in_executor(worker)  ──→  ThreadPoolExecutor (max_workers=4)
       │                                           │
       │                                           └─ sync_work(on_progress=cb)
       │                                                  │
       │  ┌───────────────────────────────────────────────┘
       │  │  call_soon_threadsafe(queue.put_nowait, ...)
       │  ▼
       ├─ await queue.get()  ──→  yield SSE event
       └─
```

### 5.2 取消处理

客户端断开连接时，FastAPI 取消协程（`CancelledError`）。后台线程**不会被中断**——让它静默跑完。Phase 2 暂不做后台任务取消（复杂度过高，且本地工具场景下极少发生）。

---

## 6. 决策记录

| # | 决策 | 结论 |
|---|------|------|
| D1 | SSE 协议格式 | 标准 `text/event-stream`（`event:` + `data:` 行） |
| D2 | 事件类型区分 | `progress` / `result` / `error` 三种 |
| D3 | 进度总数 | `total: -1` 表示不确定进度 |
| D4 | 线程池 | `max_workers=4`（本地工具，并发低） |
| D5 | 取消策略 | Phase 2 不做后台任务取消 |
| D6 | 错误码前缀 | `E_` = error, `W_` = warning |
| D7 | 请求方式 | 操作类统一 POST；非 RESTful URL 参数 |
| D8 | 路径输入 | 路由层收到后统一过 `path_resolver` |

---

## 7. 前端消费约定

### 7.1 SSE 客户端

前端使用 `fetch` + `ReadableStream` 消费 SSE 流（`frontend/src/api/sse.ts`）。

约束：
- 支持 `onProgress` / `onResult` / `onError` 回调
- 连接断开时自动重连**禁止**（每次操作是单次执行，断开意味着操作终止）
- 解析失败时上报错误，不静默丢弃

### 7.2 REST 客户端

使用 `fetch` 封装（`frontend/src/api/client.ts`）。

约束：
- 统一错误处理：非 `ok` 响应 → 提取 `errors` 并展示
- 超时不适于长耗时端点（长耗时走 SSE）

---

## 8. 未来扩展预留

| 方向 | 预留空间 |
|------|----------|
| WebSocket | SSE 的 `step` 标识可复用于 WebSocket 消息路由。若未来引入双向通信，在现有事件类型基础上增加 `request` 类型即可，不破坏已有协议 |
| 二进制进度 | `progress` 事件当前为纯 JSON；若需传输二进制帧（如截图预览），可增加 `event: binary` 通道，不影响现有 JSON 事件 |
| Tauri2 IPC | `ApiResponse` 结构可直接用于 Tauri `invoke` 返回值，SSE 替换为 Tauri `emit` 事件 |

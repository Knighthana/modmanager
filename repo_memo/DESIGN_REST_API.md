# REST API 设计

> Status: stable
> Authority: authoritative
> Read-Tier: task-scoped
> Purpose: 约束 Web API 的接口形态、SSE 通信方式与 Web 层行为边界

> **维护说明（2026-05-06）**：本文档仍作为 Web 层的现行规范使用。
> 其中早期设计中的 `"forest"` key 在 P0 后已统一改为 `"trees"`，`PipelineResult.forest` 已改为 `PipelineResult.trees`。
> 涉及映射输出结构时，以 `repo_memo/DESIGN_FOREST_MODEL.md` 定义的现行输出契约为准；其余 Web API 行为约束以本文档为准。

创建：2026-04-30
实现状态：已落地并持续生效
所有 7 个决策已确认

---

## 0. 前置决策汇总

| Q# | 决策 |
|-----|------|
| Q1 | **FastAPI** — 现代异步，自动 OpenAPI 文档，Pydantic 校验 |
| Q2 | **全部 6 个操作暴露** — discover_user_config / generate_database / compute / backup / apply / run |
| Q3 | **纯本地 localhost** — 仅监听 127.0.0.1，无认证 |
| Q4 | **全异步 I/O** — 长耗时操作通过 SSE 推送进度；UI 线程不阻塞 |
| Q5 | **独立子包 `modmanager_web`** — 与 CLI 包解耦，可选 extras 安装 |
| Q6 | **适配层** — PipelineResult 外裹 `ApiResponse`，REST 友好，便于扩展 |
| Q7 | **方案 A（独立对等）** — CLI 和 Web 各自独立调用 orchestrator，共享内核模式，耦合度最低 |

---

## 1. Q7: CLI 与 Web API 的关系分析

### 方案 A: CLI 直接调 orchestrator，Web API 也直接调 orchestrator（独立对等）

```
                    ┌─────────────────────┐
           CLI  →   │    orchestrator      │   ←  Web API / GUI
                    │  (共享服务层)          │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │      bootstrap        │
                    └──────────────────────┘
```

**优点**：
1. CLI 零额外依赖——不引入 HTTP 客户端库，启动快，适合脚本化和 CI/CD
2. 离线可用——不依赖 Web 服务运行，符合 CLI 工具的直觉
3. orchestrator 作为共享服务层，行为一致性由它天然保证
4. 改动局限于各自入口，互不影响

**风险**：
1. CLI 和 Web 的输出格式可能各自实现，长期可能分化
2. 测试需覆盖两条调用路径（可以通过测试 orchestrator 本身来减轻）
3. 如果未来引入会话/状态管理，需要在 orchestrator 层统一，而非在某一入口

### 方案 B: CLI 改为调 Web API

```
         CLI  ──(HTTP)──→  Web API  ──→  orchestrator  ──→  ...
         GUI  ──(HTTP)──→
```

**优点**：
1. 单一后端——"怎么做"的逻辑只存在于 Web API 一处
2. 远程管理成为可能——CLI 可操作另一台机器上的 modmanager
3. 行为天然一致——CLI 和 Web GUI 走同一条 HTTP 路径

**风险**：
1. CLI 必须依赖 HTTP 服务运行 → **失去脚本/离线能力**
2. 引入 HTTP 客户端依赖（httpx / requests），增加安装体积
3. CLI 启动需等待服务可用，增加延迟和错误面
4. 对于本机快速操作（如 compute），走 HTTP 是无谓的中间层
5. **Web 服务挂了 → CLI 也挂了**

### 方案 C: 混合 — CLI 默认直接调，可选 `--remote` 连 Web API

**优点**：
1. 两全其美：本地快 + 远程可管理
2. 用户可根据场景选择

**风险**：
1. 实现复杂度最高——CLI 需维护两套调用路径 + 输出格式化
2. 输出格式对齐成本高——直接调返回 dict，HTTP 返回 JSON，需统一适配
3. 两套路径行为微差异难以发现和修复
4. 对 Phase 2 目标（暴露 REST API）来说过度设计

### 决策：方案 A（已确认 ✅）

**耦合度分析**：
- 方案 A 是**共享内核（Shared Kernel）**模式：CLI 和 Web API 各自独立消费 orchestrator
- CLI ↔ Web API **零依赖**，互不知晓对方的存在
- orchestrator 的 `PipelineResult` 是唯一契约，两边各自适配为自己的输出格式——这不构成耦合
- 无需再拆分：orchestrator 只返回结构体（不负责格式化），业务逻辑已是单一真相源

理由：
- Phase 2 的目标是 **"把功能暴露为 REST API"**，而非重构 CLI
- orchestrator 已提供完美共享服务层，两套入口共享同一套业务逻辑
- CLI 和 Web 互不依赖，各自简单，符合 KISS
- 未来若需要远程管理，可在 Phase 3 引入 `--remote`（彼时再评估方案 C）

---

## 2. 架构总览

```
                            ┌──────────────────────────────────┐
                            │        modmanager_web              │
                            │  ┌────────────┐  ┌─────────────┐ │
   浏览器 / Web GUI ──(HTTP)──→│  FastAPI    │  │   SSE       │ │
                            │  │  routes     │  │  Progress   │ │
                            │  └─────┬──────┘  │  Streaming   │ │
                            │        │         └─────────────┘ │
                            │  ┌─────▼──────┐                  │
                            │  │  adapters   │  ApiResponse    │
                            │  │  schemas    │  Pydantic       │
                            │  └─────┬──────┘                  │
                            └────────┼──────────────────────────┘
                                     │  import
                            ┌────────▼──────────────────────────┐
                            │      modmanager                │
                            │  orchestrator / bootstrap          │
                            │  engine / aggregator / backup_ops  │
                            └───────────────────────────────────┘
```

- **`modmanager_web`**：纯 HTTP 层。不做业务逻辑，仅做参数接收、格式适配、SSE 流式转发。
- **`modmanager`**：底层模块无改动。orchestrator 和 bootstrap 的 `ProgressCallback` Protocol 已经为 SSE 桥接预留了接口。

---

## 3. 包结构

```
src/modmanager_web/
├── __init__.py          # 包声明，导出 create_app
├── __main__.py          # uvicorn 启动入口: `python -m modmanager_web`
├── app.py               # FastAPI 应用工厂 + 路由注册
├── routes/
│   ├── __init__.py
│   ├── config.py        # discover_user_config 路由
│   ├── database.py      # generate_database 路由
│   └── pipeline.py      # compute / backup / apply / run 路由
├── schemas.py           # Pydantic 请求/响应模型
├── adapters.py          # PipelineResult → ApiResponse 转换
└── sse.py               # SSE 进度流式输出工具
```

### 依赖（optional extras）

`pyproject.toml` 新增：
```toml
[project.scripts]
modmanager-web = "modmanager_web.__main__:main"

[project.optional-dependencies]
web = [
    "fastapi>=0.100",
    "uvicorn[standard]>=0.23",
]
```

安装方式：`pip install ".[web]"`

---

## 4. REST API 端点设计

### 4.1 响应格式（适配层）

所有非 SSE 端点返回：

```json
{
  "ok": true,
  "data": { ... },
  "errors": [],
  "warnings": []
}
```

所有 SSE 端点：`text/event-stream`，最终事件包含同样的结构。

### 4.2 端点清单

| 方法 | 路径 | 说明 | 响应类型 |
|------|------|------|----------|
| `GET` | `/api/health` | 健康检查 | JSON |
| `POST` | `/api/config/discover` | 加载 user_config.json | JSON |
| `POST` | `/api/config/save` | 保存 user_config（含 rule_sources 路径归一化） | JSON |
| `POST` | `/api/database/generate` | 扫描 Steam 库生成 database.json（纯数据，无 managed） | SSE |
| `POST` | `/api/database/load` | 从路径加载 database.json | JSON |
| `POST` | `/api/database/save` | 保存 database（移除 managed 校验；用于高级页编辑） | JSON |
| `POST` | `/api/pipeline/compute` | 计算映射；优先读 aggregated_rule_path（跳过聚合），回退 kmm_rule_paths；接受可选 managed_entries | SSE |
| `POST` | `/api/pipeline/backup` | 差异备份 | SSE |
| `POST` | `/api/pipeline/apply` | 应用替换 | SSE |
| `POST` | `/api/pipeline/run` | 全流水线（聚合→计算→备份→应用） | SSE |
| `POST` | `/api/pipeline/restore` | 从备份恢复文件 | SSE |
| `POST` | `/api/pipeline/visualize` | Forest JSON → SVG 可视化 | JSON |
| `POST` | `/api/rules/scan` | 扫描目录列出 `*.kmmrule.json` 文件 | JSON |
| `POST` | `/api/rules/read` | 读取单个 kmmrule 文件内容 | JSON |
| `POST` | `/api/rules/aggregate` | 【新】聚合选定规则文件 → aggregated_rule_set.json | SSE |
| `POST` | `/api/rules/affected-entries` | 【新】查询聚合规则影响的 game/mod（供计算准备页） | JSON |
| `POST` | `/api/rules/load-aggregated` | 【新】加载 aggregated_rule_set.json 原文（供高级页） | JSON |
| `GET` | `/api/workspace/status` | 【新】获取 workspace.json 全部内容 | JSON |
| `POST` | `/api/workspace/save-inputs` | 【新】更新 workspace inputs | JSON |
| `POST` | `/api/workspace/save-decisions` | 【新】保存 branch_decisions | JSON |
| `POST` | `/api/workspace/save-results` | 【新】保存 compute 结果摘要 + inputs_hash | JSON |
| `POST` | `/api/backups/list` | 列出备份目录摘要 | JSON |
| `POST` | `/api/backups/inspect` | 查看备份详情 | JSON |

### 4.3 端点详设

#### `GET /api/health`

```json
// → 200
{
  "ok": true,
  "data": { "version": "0.1.0", "package": "modmanager_web" },
  "errors": [],
  "warnings": []
}
```

#### `POST /api/config/discover`

```json
// ← Request
{
  "home_dir": null   // string | null，null = 自动检测
}

// → 200
{
  "ok": true,
  "data": { /* 合并后的 user_config 字典 */ },
  "errors": [],
  "warnings": []
}

// → 500 (FileNotFoundError)
{
  "ok": false,
  "data": null,
  "errors": ["No user_config.json found in any search location"],
  "warnings": []
}
```

#### `POST /api/database/generate`

```json
// ← Request
{
  "mode": "auto",             // "auto" | "manual"
  "paths": null,              // string[] | null (manual 模式必填)
  "working_pathstyle": "linux",
  "greedy_parsing": false,
  "cache_path": null          // string | null
}

// → SSE stream
event: progress
data: {"step":"scan","finished":0,"total":-1,"message":"Discovering Steam libraries..."}

event: progress
data: {"step":"scan","finished":1,"total":1,"message":"Steam discovery complete"}

event: result
data: {"ok":true,"data":{/* database dict */},"errors":[],"warnings":[]}
```

#### `POST /api/database/save`

校验 managed 约束后写入 database.json。请求体包含完整 database 字典和目标输出路径。

```json
// ← Request
{
  "database": { /* database dict，含 game[].managed 和 mod[].managed */ },
  "output_path": "/tmp/modmanager_database_generated.json"
}

// → 200 (成功)
{
  "ok": true,
  "data": {
    "path": "/tmp/modmanager_database_generated.json",
    "database": { /* 清洗后的 database dict——E_DUPLICATE 错误在对应冲突组全部解决后被移除 */ }
  },
  "errors": [],
  "warnings": []
}

// → 200 (校验失败)
{
  "ok": false,
  "data": null,
  "errors": [
    "E_DUPLICATE_APPID: game[3] appid=270150 的 managed=true 与 game[5] 冲突，同一 appid 最多一个 managed=true"
  ],
  "warnings": []
}
```

**校验规则**：
- 同一 `appid` 的 game 条目中，最多一个 `managed: true`
- 同一 `mixed_id` 的 mod 条目中，最多一个 `managed: true`
- 校验通过后，条件清除已解决的 `E_DUPLICATE_APPID` / `E_DUPLICATE_MIXED_ID` 错误：
  - 仅当**该类型所有重复组**都恰好有一个 `managed: true` 时才清除对应错误
  - 未解决的重复组错误保留

**同步语义**：前端在成功响应中获取 `data.database` 覆盖本地 store（见 DESIGN_STORAGE.md §8.5.1）；不应使用请求中的原始 database 更新本地状态。

#### `POST /api/pipeline/compute`

```json
// ← Request
{
  "database": { /* database dict */ },
  "kmm_rule_paths": ["/path/to/rule1.json", "/path/to/rule2.json"],
  "user_config_path": "/path/to/user_config.json",
  "action_orders": null,        // dict | null
  "branch_decisions": null      // dict | null
}

// → SSE stream  → event: progress ... → event: result
```

#### `POST /api/pipeline/run`

```json
// ← Request
{
  "database": { /* ... */ },
  "kmm_rule_paths": ["/path/to/rule1.json"],
  "user_config_path": "/path/to/user_config.json",
  "backup_dir": "/path/to/backup_dir",
  "action_orders": null,
  "branch_decisions": null,
  "dry_run": false          // true → 仅聚合+计算，跳过 backup 和 apply（不碰磁盘）
}
```

> **dry_run 语义**：
> - `false`（默认）：完整流水线：聚合 → 计算 → 备份 → 应用
> - `true`：仅聚合+计算，**不执行备份和应用的任何磁盘 I/O**。适用于"先看看映射结果"的场景
> - 若需要"仅备份不应用"，应分别调用 `/api/pipeline/compute` + `/api/pipeline/backup`

```json
// → SSE stream
event: progress
data: {"step":"aggregate","finished":0,"total":1,"message":"Aggregating rules..."}

event: progress
data: {"step":"aggregate","finished":1,"total":1,"message":"Rule aggregation complete"}

event: progress
data: {"step":"compute","finished":0,"total":1,"message":"Computing mapping..."}

...

event: result
data: {
  "ok": true,
  "data": {
    "forest": [...],
    "final_mapping": [...],
    "stats": {
      "backed_up": 42,
      "applied": 42,
      "skipped": 0
    }
  },
  "errors": [],
  "warnings": []
}
```

---

## 5. SSE 进度桥接设计

核心挑战：orchestrator 的同步 `ProgressCallback(step, finished, total, message)` 需要桥接到 FastAPI 的异步 `StreamingResponse`。

### 5.1 方案：asyncio.Queue 桥接

```python
# sse.py（伪代码结构）

import asyncio
import json
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4)

async def stream_with_progress(
    sync_work: callable,  # 接受 on_progress 回调，返回结果
    *,
    sse_event_prefix: str = "pipeline",
) -> AsyncGenerator[str, None]:
    """在后台线程执行同步工作，通过 asyncio.Queue 桥接进度到 SSE 流。

    SSE 事件类型：
      - `event: progress` — 进度更新
      - `event: result`   — 最终结果
      - `event: error`    — 异常
    """
    queue: asyncio.Queue = asyncio.Queue()

    def progress_cb(step, finished, total, message=""):
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {"type": "progress", "step": step, "finished": finished, "total": total, "message": message}
        )

    def worker():
        try:
            result = sync_work(on_progress=progress_cb)
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "result", "payload": result})
        except Exception as exc:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(exc)})

    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, worker)

    try:
        while True:
            item = await queue.get()
            if item["type"] == "progress":
                yield f"event: progress\ndata: {json.dumps(item)}\n\n"
            elif item["type"] == "result":
                adapted = adapt_pipeline_result(item["payload"])
                yield f"event: result\ndata: {json.dumps(adapted)}\n\n"
                return
            elif item["type"] == "error":
                yield f"event: error\ndata: {json.dumps({'ok': False, 'errors': [item['message']]})}\n\n"
                return
    except asyncio.CancelledError:
        # 客户端断开连接——后台线程无法取消，只能让它跑完。
        # Phase 2 暂不做后台任务取消（复杂性过高）。
        pass
```

### 5.2 路由使用示例

```python
# routes/pipeline.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from modmanager.orchestrator import run as orch_run
from ..schemas import RunRequest
from ..sse import stream_with_progress

router = APIRouter()

@router.post("/run")
async def pipeline_run(req: RunRequest):
    def do_work(on_progress):
        return orch_run(
            database=req.database,
            kmm_rule_paths=req.kmm_rule_paths,
            user_config_path=req.user_config_path,
            backup_dir=req.backup_dir,
            action_orders=req.action_orders,
            branch_decisions=req.branch_decisions,
            dry_run=req.dry_run,
            on_progress=on_progress,
        )
    return StreamingResponse(
        stream_with_progress(do_work),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
```

### 5.3 注意事项

1. **线程安全**：`call_soon_threadsafe` 是 asyncio 的推荐方式，线程安全
2. **取消处理**：Phase 2 暂不实现后台任务取消。客户端断开时，后台线程会继续跑完（无法安全中断底层 I/O 操作）
3. **线程池大小**：`max_workers=4` 适合本地工具（同时最多 4 个并发操作），可按需调整

---

## 6. Pydantic Schema 设计（schemas.py）

```python
from pydantic import BaseModel, Field
from typing import Any

# ── 通用 ──
class ApiResponse(BaseModel):
    ok: bool
    data: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

# ── config ──
class DiscoverUserConfigRequest(BaseModel):
    home_dir: str | None = None

# ── database ──
class GenerateDatabaseRequest(BaseModel):
    mode: str = "auto"                    # "auto" | "manual"
    paths: list[str] | None = None
    working_pathstyle: str = "linux"
    greedy_parsing: bool = False
    cache_path: str | None = None

# ── pipeline ──
class ComputeRequest(BaseModel):
    database: Any              # dict（数据库内容）| str（database.json 路径，后端自行解析）
    kmm_rule_paths: list[str]
    user_config_path: str
    action_orders: dict[str, int] | None = None
    branch_decisions: dict[str, str] | None = None

class BackupRequest(BaseModel):
    mapping_result: dict[str, Any]        # compute_mapping 的原始输出
    backup_dir: str

class ApplyRequest(BaseModel):
    final_mapping: list[dict[str, Any]]
    backup_dir: str
    dry_run: bool = False

class RunRequest(BaseModel):
    database: Any              # dict（数据库内容）| str（database.json 路径，后端自行解析）
    kmm_rule_paths: list[str]
    user_config_path: str
    backup_dir: str
    action_orders: dict[str, int] | None = None
    branch_decisions: dict[str, str] | None = None
    dry_run: bool = False
```

---

## 7. 适配层设计（adapters.py）

```python
from modmanager.orchestrator import PipelineResult
from .schemas import ApiResponse

def adapt_pipeline_result(pr: PipelineResult) -> dict:
    """将 PipelineResult 转为 ApiResponse 序列化格式。"""
    return {
        "ok": pr.ok,
        "data": {
            "forest": pr.forest,
            "final_mapping": pr.final_mapping,
            "mapping_result": pr.mapping_result,
            "stats": {
                "backed_up": len(pr.backup_result.get("backed_up", [])) if pr.backup_result else 0,
                "applied": len(pr.apply_result.get("applied", [])) if pr.apply_result else 0,
                "skipped": len(pr.apply_result.get("skipped", [])) if pr.apply_result else 0,
            } if pr.backup_result or pr.apply_result else None,
        },
        "errors": pr.errors,
        "warnings": pr.warnings,
    }

def adapt_backup_result(result: dict) -> dict:
    return {
        "ok": result.get("ok", False),
        "data": {
            "backed_up": result.get("backed_up", []),
            "skipped": result.get("skipped", []),
        },
        "errors": result.get("errors", []),
        "warnings": [],
    }

def adapt_apply_result(result: dict) -> dict:
    return {
        "ok": result.get("ok", False),
        "data": {
            "applied": result.get("applied", []),
            "skipped": result.get("skipped", []),
        },
        "errors": result.get("errors", []),
        "warnings": [],
    }

def adapt_dict_result(data: dict) -> dict:
    """适配 discover_user_config / generate_database 的返回。"""
    return {
        "ok": True,
        "data": data,
        "errors": [],
        "warnings": [],
    }

def adapt_error(message: str) -> dict:
    return {
        "ok": False,
        "data": None,
        "errors": [message],
        "warnings": [],
    }
```

---

## 8. FastAPI 应用工厂（app.py）

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import config, database, pipeline

def create_app() -> FastAPI:
    app = FastAPI(
        title="ModManager Web API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # 仅本地访问，但未来可能扩展 → 先默认开放 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health():
        from .adapters import adapt_dict_result
        return adapt_dict_result({"version": "0.1.0", "package": "modmanager_web"})

    app.include_router(config.router, prefix="/api/config", tags=["config"])
    app.include_router(database.router, prefix="/api/database", tags=["database"])
    app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])

    return app
```

### 启动入口（`__main__.py`）

```python
import uvicorn
from .app import create_app

def main():
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    main()
```

启动：`python -m modmanager_web` 或 `modmanager-web`

---

## 9. 对现有代码的改动

| 模块 | 改动 |
|------|------|
| `modmanager/*` | **无改动** |
| `pyproject.toml` | 新增 `web` extras + `modmanager-web` 入口 |
| `__init__.py` | 已在 Phase 1 更新，无需再改 |

### pyproject.toml 改动

```toml
[project.scripts]
modmanager-cli = "modmanager.cli:main"
modmanager-web = "modmanager_web.__main__:main"       # 新增

[project.optional-dependencies]
web = [
    "fastapi>=0.100",
    "uvicorn[standard]>=0.23",
]
```

---

## 10. 实现顺序

```
Task 9:  schemas.py + adapters.py    ← Pydantic 模型 + 适配器
Task 10: sse.py                       ← 进度桥接基础设施
Task 11: routes/ (config + database + pipeline)  ← 路由实现
Task 12: app.py + __main__.py         ← 应用工厂 + 启动入口
Task 13: pyproject.toml 更新          ← extras + 入口点
Task 14: 测试                         ← 见 §11
```

---

## 11. 测试设计

### 12.1 测试文件

新建 `tests/test_web_api.py`（无需 FastAPI 启动真实服务器，全部使用 `TestClient`）。

### 12.2 测试用例（≥10 个）

| # | 测试名 | 覆盖 |
|---|--------|------|
| 1 | `test_health_endpoint` | GET /api/health → 200, ok=true |
| 2 | `test_discover_user_config_success` | POST /api/config/discover → 200, 含合并后的 config |
| 3 | `test_discover_user_config_not_found` | 三级均无 config → 500, errors 非空 |
| 4 | `test_generate_database_invalid_mode` | mode="invalid" → 500 |
| 5 | `test_compute_pipeline_sse` | POST /api/pipeline/compute → SSE 流含 progress + result |
| 6 | `test_run_pipeline_sse` | POST /api/pipeline/run → SSE 流含 progress + result |
| 7 | `test_adapt_pipeline_result_ok` | PipelineResult(ok=True) → ApiResponse.ok=True |
| 8 | `test_adapt_pipeline_result_fail` | PipelineResult(ok=False, errors=["E_X"]) → errors 传递 |
| 9 | `test_adapt_backup_result` | backup_ops 返回值 → ApiResponse 结构正确 |
| 10 | `test_sse_stream_disconnect` | 客户端断开 → 服务端不崩溃 |
| 11 | `test_docs_endpoint` | GET /api/docs → 200, HTML 含 "Swagger" |

### 12.3 测试基础设施

- 使用 FastAPI 内置的 `TestClient`（无需启动 uvicorn）
- 为 `discover_user_config` 测试创建临时 `user_config.json`（`tmp_path` fixture）
- 为 SSE 测试验证 `text/event-stream` 内容
- Mock orchestrator / bootstrap 中有副作用的调用，避免修改真实文件系统

### 12.4 测试中不做什么

- 不启动真实 HTTP 服务器（TestClient 即可）
- 不修改已有测试文件（261 tests 必须保持通过）
- 不测试 orchestrator/bootstrap 的业务逻辑（已在 Phase 1 覆盖）

---

## 12. 验收标准

1. `pip install ".[web]"` 后 `modmanager-web` 命令可启动服务
2. 浏览器访问 `http://127.0.0.1:8000/api/docs` 可见 Swagger UI
3. `POST /api/config/discover` 返回 user_config
4. `POST /api/pipeline/compute` SSE 流正确返回进度 + 结果
5. `POST /api/pipeline/run` 全流水线 SSE 流正确
6. 已有 CLI 测试（261）不被破坏

---

## 5. Web 层安全约定

> 更新：2026-05-08 质量审计

### 应用定性

本项目为**本地应用**，Web 层仅作跨平台 GUI 的实现手段（控制面板），并非公网 Web 服务。
用户 = 机器的所有者，对本机文件有完整读写权限，不存在越权访问问题。

唯一真实的外部威胁：用户浏览器中的恶意网页向 `127.0.0.1:8000` 发跨域请求，
在用户不知情的情况下触发 backup/apply 等操作（与文件读写权限无关，是操作触发问题）。
CORS 配置的目的仅为阻断此类场景，不是访问控制手段。
路径规范化的目的是"输入归一化"，不是"访问限制"。

### 5.1 CORS 策略

- **禁止** `allow_origins=["*"]`
- 检测逻辑：复用 `static_dir.exists()` 判断（已用于静态文件挂载）
  - `frontend/dist/` 存在（生产态） → 不挂载 CORS 中间件（同 origin，无需）
  - `frontend/dist/` 不存在（开发态） → 允许 `["http://localhost:5173", "http://127.0.0.1:5173"]`
- 开发者零配置，无需 `.env` 文件
- **Tauri2 迁移预留**：届时追加 `tauri://localhost`（macOS/Linux）和 `https://tauri.localhost`（Windows）
  实现：通过环境变量 `KMM_CORS_ORIGINS`（逗号分隔）覆盖开发态默认值

### 5.2 路径输入规范化（Web 路由入口）

**定性：输入归一化，不是访问控制。** 本地应用用户对自己的文件有完整权限。

原则：所有原始用户路径输入在 Web 路由层过且仅过一遍 `path_resolver`，之后视为规范路径。
下游模块（orchestrator/engine 等）只做合规性断言，不再猜测路径。

读类入口（目标必须存在）：

| 路由文件 | 字段 | 使用函数 |
|----------|------|----------|
| `routes/rules.py` `/read` | `req.path` | `resolve_file_path` |
| `routes/rules.py` `/scan` | `req.dir` | `resolve_directory_path` |
| `routes/backups.py` `/list` | `req.dir` | `resolve_directory_path` |
| `routes/pipeline.py` `/compute` `/run` | `req.kmm_rule_paths[]` | `resolve_file_path`（每项） |
| `routes/pipeline.py` `/compute` `/run` | `req.user_config_path` | `resolve_file_path` |

写类入口（目标不一定存在，不走 `path_resolver`）：

| 路由文件 | 字段 | 处理方式 |
|----------|------|----------|
| `routes/config.py` `/save` | `req.output_path` | `Path(output_path).expanduser().resolve()`（纯规范化） |

`path_resolver` 抛出异常时，路由层捕获并返回 `{"ok": false, "errors": [...]}`，
SSE 端点中异常会被 `stream_with_progress` 捕获并作为 SSE error 事件推送（原始错误信息保留，对本地用户有调试价值）。

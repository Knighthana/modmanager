# Tasklist

## ✅ Completed

### M1 Core + Patches
- 核心映射引擎（6 条规则 + 环检测 + 分枝）✅
- `def_destin`/`def_action` 继承移交聚合器 ✅
- sub 鉴权移交聚合器，移除 `validate_forest_roots` ✅
- 同 mod 内 actionlist 自动裁决（later wins）✅
- delete 叶折叠 ✅
- `provenance_ref` / `action_order` / `sidecar_ref` 在 changerequest 中传导 ✅

### 备份/替换/恢复（Phases 7–13）
- 差异备份、替换执行、从备份恢复 ✅
- 脏数据检测、冲突检查、orphan 治理 ✅

### 聚合器
- 完整聚合器实现（6 步流水线）✅
- 权限鉴权（game + sub）✅
- 多规则合并策略 ✅

### Forest 可视化
- ASCII / DOT / DOT→SVG / HTML standalone ✅

### Steam 发现与数据库
- 多库发现、CRUD、liveupdate/regen ✅

---

## Phase 1: Bootstrap & Orchestrator ✅

在 Web GUI 之前，需要初始化和调度层把现有模块串成端到端流水线。

### 已完成的模块

| 模块 | 文件 | 职责 |
|------|------|------|
| Bootstrap | `src/modmanager_cli/bootstrap.py` ✅ | user_config 三级搜索+合并、Steam 数据库生成 |
| Orchestrator | `src/modmanager_cli/orchestrator.py` ✅ | 流水线调度：接收初始状态，按序驱动聚合→映射→备份→应用；支持进度回调；预留多游戏并行调度扩展点 |
| CLI 适配 | `src/modmanager_cli/cli.py` ✅ | `_handle_backup`/`_handle_apply` 改为调用 orchestrator |
| 测试 | `tests/test_bootstrap.py` ✅ (11 tests) | `tests/test_orchestrator.py` ✅ (7 tests) |

各子模块（engine、aggregator、backup_ops）独立存在、可单独测试，orchestrator 只做编排。

### 决策记录
全部 8 个问题已决策：见 `repo_memory/direct/QUESTIONS_BOOTSTRAP.md`

---

## Phase 2: Web API 层 ✅

将 bootstrap + engine + backup 暴露为 REST 接口。

设计文档：`repo_memory/direct/DESIGN_PHASE2_WEB_API.md`
决策记录：7 个问题全部已确认 ✅（含 Q7 方案 A 独立对等）

### 已完成的模块（`modmanager_web` 独立子包）

| 模块 | 文件 | 职责 |
|------|------|------|
| Schemas | `src/modmanager_web/schemas.py` ✅ | Pydantic 请求/响应模型 |
| Adapters | `src/modmanager_web/adapters.py` ✅ | PipelineResult → ApiResponse 转换 |
| SSE Bridge | `src/modmanager_web/sse.py` ✅ | 同步 ProgressCallback → 异步 SSE 流桥接 |
| Routes | `src/modmanager_web/routes/{config,database,pipeline}.py` ✅ | REST 端点 |
| App | `src/modmanager_web/app.py` ✅ | FastAPI 应用工厂 |
| Entry | `src/modmanager_web/__main__.py` ✅ | uvicorn 启动 |
| 测试 | `tests/test_web_api.py` ✅ (15 tests) | |

全量 276 tests 通过（261 existing + 15 new）。`modmanager_cli/*` 零改动。

## Phase 3: 前端 GUI ✅

规则浏览器、Forest 可视化嵌入、冲突裁决 UI、备份/恢复控制台。

决策记录：`repo_memory/direct/QUESTIONS_PHASE3.md`（13 个问题全部已决策 ✅）
设计文档：`repo_memory/direct/DESIGN_PHASE3_GUI.md`

### 需要新增的模块

| 模块 | 位置 | 职责 |
|------|------|------|
| Vue SPA | `frontend/` | Vue 3 + Vite + TypeScript + Element Plus + Pinia |
| M3 前置 | `forest_visual.py`（修改） | SVG 节点嵌入交互属性 |
| 静态挂载 | `app.py`（修改） | FastAPI StaticFiles + SPA fallback |

### 四个页面

| 页面 | 路由 | 职责 |
|------|------|------|
| ForestPage | `/forest` | 参数表单 + Forest SVG 展示 + zoom/pan + SSE 进度 |
| ConflictsPage | `/conflicts` | 冲突列表 + 候选选择 + 重新计算 |
| RulesPage | `/rules` | kmm_rule 文件浏览 |
| BackupPage | `/backup` | 备份列表 + 恢复操作 |

### 测试
- 前端 Vitest: 14 tests 全部通过
- Python: 276 tests 全部通过
- frontend/ 构建成功，产物嵌入 FastAPI 静态文件

---

## Future（远期）

### Forest Visualization Expansion（M3）
- Plot renderer
- trace/meta 扩展字段兼容验证

### GUI Visualization And Interaction（M4）
- hover 整链高亮
- 分叉节点超链接与详情展示
- 用户选枝 UI
- 插件运行链
- 老浏览器 fallback

### 其他
- 自定义脚本调用（危险操作，仅允许资深用户）
- base64 导入规则
- VDF/ACF 文件格式深度解析增强
